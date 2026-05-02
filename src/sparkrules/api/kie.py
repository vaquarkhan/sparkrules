"""
KIE Server REST compatibility (expanded subset).

Implements Drools-aligned JSON shapes clients expect: ``SUCCESS`` / ``FAILURE``
:class:`ServiceResponse` wrappers, container lifecycle (deploy / dispose / introspect),
globals in stateless batches, and rule execution hooks.

Not a drop-in replica of legacy KIE in one release—grow coverage intentionally.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from sparkrules.compiler.discrimination import DiscriminationNetwork
from sparkrules.parser import parse_rules
from sparkrules.runtime.rule_chain import ChainExecutionPolicy, run_rule_chain

router = APIRouter(prefix="/kie-server/services/rest", tags=["kie-server"])

_kie_containers: dict[str, str] = {}
_kie_globals: dict[str, dict[str, Any]] = defaultdict(dict)


def reset_kie_containers_for_tests() -> None:
    _kie_containers.clear()
    _kie_globals.clear()


def _service_ok(result: Any) -> dict[str, Any]:
    return {"type": "SUCCESS", "msg": "", "result": result}


def _service_failure(msg: str, result: Any = None) -> dict[str, Any]:
    return {"type": "FAILURE", "msg": msg, "result": result}


def _object_map_to_fact_fragment(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict) or len(obj) != 1:
        return {}
    cls_name, fields = next(iter(obj.items()))
    if not isinstance(cls_name, str):
        return {}
    short = cls_name.split(".")[-1]
    bind = (short[:1].lower() + short[1:]) if short else "x"
    return {bind: fields if isinstance(fields, dict) else {}}


def _apply_batch_commands(container_id: str, commands: list[Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fact: dict[str, Any] = {}
    globals_mut = _kie_globals[container_id]
    side_notes: list[dict[str, Any]] = []

    def _consume_insert(ins: dict[str, Any]) -> None:
        obj = ins.get("object")
        frag = _object_map_to_fact_fragment(obj)
        for k, v in frag.items():
            if k in fact and isinstance(fact[k], dict) and isinstance(v, dict):
                merged = dict(fact[k])
                merged.update(v)
                fact[k] = merged
            else:
                fact[k] = v

    def _consume_set_global(cmd: dict[str, Any]) -> None:
        sg = cmd.get("set-global")
        if isinstance(sg, dict):
            nm = sg.get("name") or sg.get("identifier") or sg.get("id")
            if isinstance(nm, str) and nm:
                obj_m = sg.get("object") or sg.get("value")
                globals_mut[nm] = obj_m

    def _consume_get_global(cmd: dict[str, Any]) -> None:
        gg = cmd.get("get-global")
        if gg is False:
            return
        if isinstance(gg, dict):
            nm = gg.get("name") or gg.get("identifier")
            side_notes.append(
                {"kind": "get-global", "name": nm or "", "value": globals_mut.get(nm or "")},
            )

    def _consume_set_focus(cmd: dict[str, Any]) -> None:
        ag = cmd.get("agenda-group-set-focus") or cmd.get("agendaGroupSetFocus")
        if isinstance(ag, dict) and isinstance(ag.get("name"), str):
            side_notes.append({"kind": "agenda-group-set-focus", "name": ag["name"]})

    def _consume_modify(mod: dict[str, Any]) -> None:
        obj = mod.get("object")
        frag = _object_map_to_fact_fragment(obj)
        for k, v in frag.items():
            fact[k] = v if isinstance(v, dict) else {}
            side_notes.append({"kind": "modify", "binding": k})

    def _consume_bpm_like(cmd: dict[str, Any]) -> None:
        """Record Drools/jBPM-style batch verbs SparkRules does not execute in stateless mode."""
        pairs = (
            ("query", "query"),
            ("start-process", "start-process"),
            ("startProcess", "start-process"),
            ("signal", "signal"),
            ("abort", "abort"),
            ("complete-work-item", "complete-work-item"),
            ("completeWorkItem", "complete-work-item"),
            ("complete-task", "complete-task"),
            ("completeTask", "complete-task"),
            ("claim-task", "claim-task"),
            ("claimTask", "claim-task"),
            ("release-task", "release-task"),
            ("releaseTask", "release-task"),
            ("delegate-task", "delegate-task"),
            ("delegateTask", "delegate-task"),
        )
        for key, label in pairs:
            if key not in cmd:
                continue
            side_notes.append({"kind": label, "payload-type": type(cmd[key]).__name__})

    def _consume_retract(retr: dict[str, Any]) -> None:
        obj = retr.get("object")
        if isinstance(obj, dict):
            frag = _object_map_to_fact_fragment(obj)
            for k in frag:
                if k in fact:
                    del fact[k]
                    side_notes.append({"kind": "retract", "binding": k})
        for key in ("handle", "out-identifier", "outIdentifier"):
            h = retr.get(key)
            if isinstance(h, str) and h and h in fact:
                del fact[h]
                side_notes.append({"kind": "retract", "binding": h})

    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        ins = cmd.get("insert")
        if isinstance(ins, dict):
            _consume_insert(ins)
        mod = cmd.get("modify")
        if isinstance(mod, dict):
            _consume_modify(mod)
        rt = cmd.get("retract")
        if isinstance(rt, dict):
            _consume_retract(rt)
        dl = cmd.get("delete")
        if isinstance(dl, dict):
            _consume_retract(dl)
        if "dispose" in cmd:
            side_notes.append({"kind": "dispose", "note": "stateless batch no-op"})
        _consume_bpm_like(cmd)
        _consume_set_global(cmd)
        _consume_get_global(cmd)
        _consume_set_focus(cmd)
        if isinstance(cmd.get("set-global"), str):
            _consume_set_global({"set-global": {"name": cmd["set-global"]}})

    globs_flat: dict[str, Any] = {f"kie_global.{k}": v for k, v in globals_mut.items()}
    merged = dict(fact)
    merged.update(globs_flat)
    return merged, side_notes


def _batch_commands_to_fact(commands: list[Any]) -> dict[str, Any]:
    """Merge insert/set-global commands into a fact-shaped dict (test helper)."""
    tid = "__kie_batch_fact__"
    try:
        merged, _ = _apply_batch_commands(tid, commands)
        return merged
    finally:
        _kie_globals.pop(tid, None)


def _fire_steps_from_commands(commands: list[Any]) -> tuple[bool, int | None]:
    """Return (needs_fire_rules, optional max). Supports fire-all / fire-until-halt synonyms."""
    need = False
    max_r = None
    _fire_keys = ("fire-all-rules", "fireUntilHalt", "fire-until-halt")
    for cmd in commands:
        if not isinstance(cmd, dict):
            continue
        fa: Any = None
        for k in _fire_keys:
            if k in cmd:
                fa = cmd[k]
                break
        if fa is None:
            continue
        need = True
        if isinstance(fa, dict) and isinstance(fa.get("max"), int):
            mx = int(fa["max"])
            max_r = mx if mx > 0 else max_r
    return need, max_r


@router.get("/server/state")
def kie_server_state() -> dict[str, Any]:
    return _service_ok({"server-state": {"status": {"value": "READY"}}})


@router.get("/server")
def kie_get_server() -> dict[str, Any]:
    return _service_ok(
        {
            "version": "1.0.1",
            "id": "sparkrules-kie-shim",
            "name": "SparkRules",
        }
    )


@router.get("/server/containers")
def kie_list_containers() -> dict[str, Any]:
    return _service_ok(
        {
            "containers": [
                {
                    "container-id": cid,
                    "release-id": {"version": "1.0", "group-id": "sparkrules", "artifact-id": "rules"},
                    "status": "STARTED",
                }
                for cid in sorted(_kie_containers)
            ]
        }
    )


@router.get("/server/containers/{container_id}", response_model=None)
def kie_describe_container(container_id: str) -> JSONResponse | dict[str, Any]:
    body = _kie_containers.get(container_id)
    if body is None:
        return JSONResponse(
            status_code=404,
            content=_service_failure(f"Could not find container {container_id!r}."),
        )
    payload = {"container-id": container_id, "drl-char-length": len(body), "status": {"value": "STARTED"}}
    return _service_ok(payload)


@router.delete("/server/containers/{container_id}")
def kie_delete_container(container_id: str) -> dict[str, Any]:
    if container_id in _kie_containers:
        del _kie_containers[container_id]
    if container_id in _kie_globals:
        del _kie_globals[container_id]
    return _service_ok({"container-status": [{"container-id": container_id, "success": True}]})


@router.put("/server/containers/{container_id}", response_model=None)
async def kie_deploy_container(container_id: str, request: Request) -> JSONResponse | dict[str, Any]:
    try:
        body_raw = await request.json()
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(err)) from err
    if not isinstance(body_raw, dict):
        return JSONResponse(
            status_code=400,
            content=_service_failure("expected JSON object for container deploy"),
        )
    body = body_raw
    drl = body.get("drl") or body.get("sparkrules-drl")
    if not drl and isinstance(body.get("config"), dict):
        items = body["config"].get("config-items") or body["config"].get("configItems")
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and str(it.get("name", "")).lower() in {
                    "drl",
                    "sparkrules-drl",
                }:
                    drl = it.get("value")
                    break
    if not isinstance(drl, str) or not drl.strip():
        return JSONResponse(
            status_code=400,
            content=_service_failure(
                "Body must include drl, sparkrules-drl, or config.config-items DRL value",
            ),
        )
    try:
        parse_rules(drl)
    except Exception as err:  # noqa: BLE001
        return JSONResponse(
            status_code=422,
            content=_service_failure(f"DRL parse error: {err}"),
        )
    _kie_containers[container_id] = drl
    return _service_ok({"container-status": [{"container-id": container_id, "success": True}]})


@router.post("/server/containers/instances/{container_id}", response_model=None)
async def kie_execute_stateless(container_id: str, request: Request) -> JSONResponse | dict[str, Any]:
    drl = _kie_containers.get(container_id)
    if drl is None:
        return JSONResponse(
            status_code=404,
            content=_service_failure(
                f"Container '{container_id}' not found. PUT /server/containers/{{id}} first."
            ),
        )
    try:
        body_raw = await request.json()
    except Exception as err:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(err)) from err
    if not isinstance(body_raw, dict):
        return JSONResponse(status_code=400, content=_service_failure("expected JSON object"))

    commands_raw = body_raw.get("commands")
    if not isinstance(commands_raw, list):
        return JSONResponse(
            status_code=400,
            content=_service_failure("expected batch 'commands' array"),
        )

    work, globals_trace = _apply_batch_commands(container_id, commands_raw)
    trigger_fire, max_iterations = _fire_steps_from_commands(commands_raw)

    inner: dict[str, Any] = {
        "work-keys": sorted(work.keys(), key=str),
        "batch-side-effects": globals_trace,
        "_kie_globals_echo": dict(_kie_globals.get(container_id, {})),
        "stopped": None,
        "final-action": {},
        "results": [],
        "skipped-fire": False,
        "fire-max-requested": max_iterations,
    }
    if trigger_fire:
        rules = parse_rules(drl)
        dn = DiscriminationNetwork.from_asts(rules) if len(rules) > 1 else None
        pol = ChainExecutionPolicy(
            stop_on_decline=False,
            max_fires=max_iterations if isinstance(max_iterations, int) and max_iterations > 0 else None,
        )
        cr = run_rule_chain(rules, work, pol, discrimination=dn)
        inner["results"] = [
            {
                "rule": s.rule_name,
                "fired": s.fired,
                "skipped": s.skipped,
                "skip-reason": s.skip_reason,
            }
            for s in cr.steps
        ]
        inner["final-action"] = cr.final_action
        inner["stopped"] = cr.stop_reason
    else:
        inner["skipped-fire"] = True

    return _service_ok(json.dumps(inner))
