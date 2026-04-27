from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import hashlib
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.staticfiles import StaticFiles

from sre.api.rulepack import build_export_payload, unified_diff_drl
from sre.api.schemas import (
    DeploymentStatusResponse,
    DqEvaluateRequest,
    DqEvaluateResponse,
    DqViolationResponse,
    GovernancePromoteRequest,
    GovernanceSyncRequest,
    GuidedFieldItem,
    RuleVersionActivePatchRequest,
    RuleVersionActiveResponse,
    RuleAssetResponse,
    RuleCreateRequest,
    RuleImportRequest,
    RuleResponse,
    RuleValidateRequest,
    RuleVersionDiffResponse,
    ChainStepResponse,
    SimulationChainRequest,
    SimulationChainResponse,
    SimulationRequest,
    SimulationResponse,
    AiSuggestRulesRequest,
    AiSuggestionResponse,
    AiMineDqRequest,
    AiAnalyzeDriftRequest,
    AiExplainRuleRequest,
    AiExplainRuleResponse,
)
from sre.ai import AiService, StubAiProvider
from sre.api.security import (
    install_optional_api_key_middleware,
    principal_from_request,
    require_any_role,
    require_tenant_match,
)
from sre.dq import DataQualityEngine
from sre.governance import PromotionRegistry, STANDARD_ENVS
from sre.governance.promote_ops import (
    sync_dev_from_active,
    validate_version_namespace,
)
from sre.dq.engine import checks_from_api, summarize_violations, to_violation_records
from sre.model.rule import new_rule_id, Rule, RuleDefinition, RuleFormat
from sre.model.rule_template import RuleTemplate
from sre.parser import parse
from sre.runtime import EngineConfig, guided_fields_from_template, runtime_conf
from sre.runtime.lineage import InMemoryLineageSink, make_lineage_event
from sre.runtime.iceberg_store import IcebergLikeTable
from sre.sim import RuleSimulator
from sre.store import (
    ConflictError,
    InMemoryRuleMetadataStore,
    RuleFilter,
    UnknownRuleError,
)


@dataclass
class AppDeps:
    store: InMemoryRuleMetadataStore = field(
        default_factory=InMemoryRuleMetadataStore
    )
    sim: RuleSimulator = field(default_factory=RuleSimulator)
    dq: DataQualityEngine = field(default_factory=DataQualityEngine)
    engine_cfg: EngineConfig = field(default_factory=EngineConfig)
    dq_violations: IcebergLikeTable = field(
        default_factory=lambda: IcebergLikeTable(
            "dq_violations",
            {
                "run_id": str,
                "fact_id": str,
                "rule_set_version": str,
                "config_fingerprint": str,
                "code": str,
                "field": str,
                "message": str,
                "severity": str,
                "scope": str,
            },
        )
    )
    dq_quarantine: IcebergLikeTable = field(
        default_factory=lambda: IcebergLikeTable(
            "dq_quarantine",
            {
                "run_id": str,
                "fact_id": str,
                "rule_set_version": str,
                "config_fingerprint": str,
                "fact_json": str,
                "critical_codes": str,
            },
        )
    )
    promotion: PromotionRegistry = field(default_factory=PromotionRegistry)
    lineage: InMemoryLineageSink = field(default_factory=InMemoryLineageSink)
    audit_log: IcebergLikeTable = field(
        default_factory=lambda: IcebergLikeTable(
            "audit_log",
            {
                "ts": str,
                "principal": str,
                "action": str,
                "resource": str,
                "request_hash": str,
                "response_status": int,
                "tenant_id": str,
            },
        )
    )
    ai: AiService = field(default_factory=lambda: AiService(StubAiProvider()))


def create_app(deps: AppDeps | None = None) -> Any:
    d = deps or AppDeps()
    app = FastAPI(title="sparkrules", version="0.1.0")

    def _hash_request_payload(payload: object) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _audit(
        req: Request,
        *,
        action: str,
        resource: str,
        tenant_id: str,
        status: int,
        payload: object,
    ) -> None:
        p = principal_from_request(req)
        d.audit_log.append(
            [
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "principal": p.principal,
                    "action": action,
                    "resource": resource,
                    "request_hash": _hash_request_payload(payload),
                    "response_status": status,
                    "tenant_id": tenant_id,
                }
            ]
        )

    def _lineage_start(run_id: str, *, inputs: dict[str, object], context: dict[str, object]) -> None:
        d.lineage.emit(
            make_lineage_event(
                "START",
                run_id,
                payload={"inputs": inputs, "context": context},
            )
        )

    def _lineage_complete(
        run_id: str,
        *,
        outputs: dict[str, object],
        metrics: dict[str, object],
    ) -> None:
        d.lineage.emit(
            make_lineage_event(
                "COMPLETE",
                run_id,
                payload={"outputs": outputs, "metrics": metrics},
            )
        )

    def _lineage_fail(run_id: str, *, exc: Exception) -> None:
        d.lineage.emit(
            make_lineage_event(
                "FAIL",
                run_id,
                payload={
                    "error_class": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/rules", tags=["rules"])
    def list_rules(req: Request) -> list[str]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {"rule_reader", "rule_author", "rule_admin", "run_operator", "dq_steward", "ai_reviewer"},
        )
        return sorted(
            {r.rule_handle for r in d.store.list(None)}
        )

    @app.post(
        "/rules", tags=["rules"], response_model=RuleResponse
    )
    def post_rule(
        req: Request,
        b: RuleCreateRequest,
    ) -> RuleResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_author", "rule_admin"})
        require_tenant_match(p, b.namespace)
        try:
            parse(b.drl)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, str(e)) from e
        t0 = datetime.now(UTC) - timedelta(days=1)
        r0 = Rule(
            rule_id=new_rule_id(),
            rule_handle=b.rule_handle,
            version=0,
            rule_group=b.group,
            salience=0,
            effective_from=t0,
            effective_to=None,
            is_active=True,
            rule_definition=RuleDefinition(
                b.drl, RuleFormat.DRL
            ),
            activation_group=None,
            namespace=b.namespace,
        )
        ins = d.store.insert(r0)
        _audit(
            req,
            action="create_rule",
            resource=f"/rules/{ins.rule_handle}/version/{ins.version}",
            tenant_id=ins.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return RuleResponse(
            rule_handle=ins.rule_handle, version=ins.version
        )

    @app.post(
        "/simulations",
        response_model=SimulationResponse,
        tags=["simulation"],
    )
    def sim(s: SimulationRequest) -> SimulationResponse:
        run_id = f"sim-{uuid.uuid4()}"
        _lineage_start(
            run_id,
            inputs={"fact": dict(s.fact)},
            context={"mode": "SIMULATION", "endpoint": "/simulations"},
        )
        try:
            f = d.sim.run(s.drl, dict(s.fact))
        except Exception as e:  # noqa: BLE001
            _lineage_fail(run_id, exc=e)
            raise
        _lineage_complete(
            run_id,
            outputs={"fired": bool(f.fired)},
            metrics={"facts_processed": 1, "rules_fired": 1 if f.fired else 0},
        )
        return SimulationResponse(
            fired=f.fired, action=f.action, bound=f.bound
        )

    @app.post(
        "/simulations/chain",
        response_model=SimulationChainResponse,
        tags=["simulation"],
    )
    def sim_chain(
        s: SimulationChainRequest,
    ) -> SimulationChainResponse:
        run_id = f"sim-chain-{uuid.uuid4()}"
        _lineage_start(
            run_id,
            inputs={"fact": dict(s.fact)},
            context={"mode": "SIMULATION_CHAIN", "endpoint": "/simulations/chain"},
        )
        sod = (
            s.stop_on_decline
            if s.stop_on_decline is not None
            else d.engine_cfg.stop_on_decline
        )
        try:
            cr = d.sim.run_chain(
                s.drl,
                dict(s.fact),
                stop_on_decline=sod,
                agenda_group_modes=dict(s.agenda_group_modes),
            )
        except Exception as e:  # noqa: BLE001
            _lineage_fail(run_id, exc=e)
            raise HTTPException(400, str(e)) from e
        c = cr.chain
        fired_count = sum(1 for st in c.steps if st.fired)
        _lineage_complete(
            run_id,
            outputs={"any_fired": bool(cr.any_fired), "stop_reason": c.stop_reason},
            metrics={"facts_processed": 1, "rules_fired": fired_count},
        )
        return SimulationChainResponse(
            any_fired=cr.any_fired,
            last_fired=c.last_fired,
            final_action=c.final_action,
            final_bound=c.final_bound,
            stop_reason=c.stop_reason,
            steps=[
                ChainStepResponse(
                    rule_name=st.rule_name,
                    fired=st.fired,
                    skipped=st.skipped,
                    skip_reason=st.skip_reason,
                    action_output=dict(st.action_output),
                    stop_on_fire=st.stop_on_fire,
                )
                for st in c.steps
            ],
        )

    @app.post("/ai/suggest-rules", response_model=list[AiSuggestionResponse], tags=["ai"])
    def ai_suggest_rules(req: Request, b: AiSuggestRulesRequest) -> list[AiSuggestionResponse]:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        made = d.ai.create_rule_suggestions(
            namespace=b.namespace,
            payload=b.model_dump(),
            principal=p.principal,
        )
        _audit(
            req,
            action="ai_suggest_rules",
            resource="/ai/suggest-rules",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return [
            AiSuggestionResponse(
                id=s.id,
                kind=s.kind,
                namespace=s.namespace,
                rule_handle=s.rule_handle,
                drl=s.drl,
                is_active=s.is_active,
                source=s.source,
                status=s.status,
                simulator_result=s.simulator_result,
                model_id=s.model_id,
            )
            for s in made
        ]

    @app.post("/ai/mine-dq-rules", tags=["ai"])
    def ai_mine_dq_rules(req: Request, b: AiMineDqRequest) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "dq_steward", "platform_admin"})
        require_tenant_match(p, b.namespace)
        payload = {"field": b.field, "facts": b.facts, "namespace": b.namespace}
        out = d.ai.provider.mine_dq_rules(payload)
        return {"items": out, "provider": d.ai.provider.provider_name}

    @app.post("/ai/analyze-drift", tags=["ai"])
    def ai_analyze_drift(req: Request, b: AiAnalyzeDriftRequest) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        return d.ai.provider.analyze_drift(b.model_dump())

    @app.post("/ai/explain-rule", response_model=AiExplainRuleResponse, tags=["ai"])
    def ai_explain_rule(req: Request, b: AiExplainRuleRequest) -> AiExplainRuleResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_reader", "rule_author", "rule_admin", "ai_reviewer", "platform_admin"})
        txt = d.ai.provider.explain_rule(b.model_dump())
        return AiExplainRuleResponse(explanation=txt)

    @app.get("/ai/suggestions", response_model=list[AiSuggestionResponse], tags=["ai"])
    def ai_suggestions(req: Request) -> list[AiSuggestionResponse]:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "rule_admin", "platform_admin"})
        rows = d.ai.store.list_pending()
        if "platform_admin" not in p.roles:
            rows = [x for x in rows if x.namespace == p.tenant_id]
        return [
            AiSuggestionResponse(
                id=s.id,
                kind=s.kind,
                namespace=s.namespace,
                rule_handle=s.rule_handle,
                drl=s.drl,
                is_active=s.is_active,
                source=s.source,
                status=s.status,
                simulator_result=s.simulator_result,
                model_id=s.model_id,
            )
            for s in rows
        ]

    @app.post("/ai/suggestions/{sid}/approve", response_model=AiSuggestionResponse, tags=["ai"])
    def ai_approve(req: Request, sid: str) -> AiSuggestionResponse:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "platform_admin"})
        s = d.ai.store.get(sid)
        require_tenant_match(p, s.namespace)
        try:
            upd = d.ai.approve(sid)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return AiSuggestionResponse(
            id=upd.id,
            kind=upd.kind,
            namespace=upd.namespace,
            rule_handle=upd.rule_handle,
            drl=upd.drl,
            is_active=upd.is_active,
            source=upd.source,
            status=upd.status,
            simulator_result=upd.simulator_result,
            model_id=upd.model_id,
        )

    @app.post("/ai/suggestions/{sid}/reject", response_model=AiSuggestionResponse, tags=["ai"])
    def ai_reject(req: Request, sid: str) -> AiSuggestionResponse:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "platform_admin"})
        s = d.ai.store.get(sid)
        require_tenant_match(p, s.namespace)
        upd = d.ai.reject(sid)
        return AiSuggestionResponse(
            id=upd.id,
            kind=upd.kind,
            namespace=upd.namespace,
            rule_handle=upd.rule_handle,
            drl=upd.drl,
            is_active=upd.is_active,
            source=upd.source,
            status=upd.status,
            simulator_result=upd.simulator_result,
            model_id=upd.model_id,
        )

    @app.get(
        "/rules/groups",
        tags=["workbench", "rules"],
    )
    def list_rule_groups() -> list[str]:
        return sorted(
            {r.rule_group for r in d.store.list(None)},
        )

    @app.get(
        "/rules/assets",
        response_model=list[RuleAssetResponse],
        tags=["workbench", "rules"],
    )
    def list_rule_assets(
        req: Request,
        q: str | None = Query(None, description="Filter: substring on handle or DRL"),
        group: str | None = Query(
            None, description="Filter: exact rule_group"
        ),
        namespace: str | None = Query(
            None, description="Filter: exact namespace (Phase 4 governance)"
        ),
    ) -> list[RuleAssetResponse]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {"rule_reader", "rule_author", "rule_admin", "run_operator", "dq_steward", "ai_reviewer"},
        )
        f: RuleFilter | None = None
        if namespace is not None and namespace != "":
            require_tenant_match(p, namespace)
            f = RuleFilter(namespace=namespace)
        elif "platform_admin" not in p.roles:
            # Default to caller tenant when no namespace filter is supplied.
            f = RuleFilter(namespace=p.tenant_id)
        rows = d.store.list(f)
        out = [
            RuleAssetResponse(
                rule_handle=r.rule_handle,
                version=r.version,
                rule_group=r.rule_group,
                namespace=r.namespace,
                salience=r.salience,
                is_active=r.is_active,
                drl=r.rule_definition.source,
            )
            for r in rows
        ]
        if q is not None and q != "":
            ql = q.lower()
            out = [
                x
                for x in out
                if ql in x.rule_handle.lower() or ql in x.drl.lower()
            ]
        if group is not None and group != "":
            out = [x for x in out if x.rule_group == group]
        return sorted(out, key=lambda x: (x.rule_handle, x.version))

    @app.patch(
        "/rules/{rule_handle}/version/{version}",
        response_model=RuleVersionActiveResponse,
        tags=["workbench", "rules"],
    )
    def patch_rule_version_active(
        req: Request,
        rule_handle: str,
        version: int,
        b: RuleVersionActivePatchRequest,
    ) -> RuleVersionActiveResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin"})
        try:
            r = d.store.get(rule_handle, version)
        except UnknownRuleError as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
        require_tenant_match(p, r.namespace)
        try:
            new = d.store.update(
                rule_handle, r.with_updates(is_active=b.is_active)
            )
        except ConflictError as e:  # noqa: BLE001
            raise HTTPException(409, str(e)) from e
        _audit(
            req,
            action="patch_rule_version_active",
            resource=f"/rules/{new.rule_handle}/version/{new.version}",
            tenant_id=new.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return RuleVersionActiveResponse(
            rule_handle=new.rule_handle,
            version=new.version,
            is_active=new.is_active,
        )

    @app.get(
        "/rules/diff",
        response_model=RuleVersionDiffResponse,
        tags=["workbench", "rules"],
    )
    def rule_version_diff(
        handle: str = Query(..., min_length=1),
        version_a: int = Query(..., ge=1),
        version_b: int = Query(..., ge=1),
    ) -> RuleVersionDiffResponse:
        try:
            ra = d.store.get(handle, version_a)
            rb = d.store.get(handle, version_b)
        except UnknownRuleError as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
        da = ra.rule_definition.source
        db = rb.rule_definition.source
        return RuleVersionDiffResponse(
            rule_handle=handle,
            version_a=version_a,
            version_b=version_b,
            drl_a=da,
            drl_b=db,
            unified_diff=unified_diff_drl(da, db),
        )

    @app.get(
        "/rules/export",
        tags=["workbench", "rules"],
    )
    def export_rule_pack() -> dict[str, Any]:
        rows = d.store.list(None)
        pack_rules = [
            {
                "rule_handle": r.rule_handle,
                "version": r.version,
                "rule_group": r.rule_group,
                "namespace": r.namespace,
                "drl": r.rule_definition.source,
            }
            for r in rows
        ]
        return json.loads(build_export_payload(pack_rules))

    @app.post(
        "/rules/import",
        tags=["workbench", "rules"],
    )
    def import_rule_pack(req: Request, b: RuleImportRequest) -> dict[str, Any]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_author", "rule_admin"})
        out: list[dict[str, object]] = []
        for it in b.items:
            require_tenant_match(p, it.namespace)
            try:
                parse(it.drl)
            except Exception as e:  # noqa: BLE001
                raise HTTPException(400, f"{it.rule_handle}: {e}") from e
        for it in b.items:
            t0 = datetime.now(UTC) - timedelta(days=1)
            r0 = Rule(
                rule_id=new_rule_id(),
                rule_handle=it.rule_handle,
                version=0,
                rule_group=it.group,
                salience=0,
                effective_from=t0,
                effective_to=None,
                is_active=True,
                rule_definition=RuleDefinition(
                    it.drl, RuleFormat.DRL
                ),
                activation_group=None,
                namespace=it.namespace,
            )
            ins = d.store.insert(r0)
            _audit(
                req,
                action="import_rule",
                resource=f"/rules/{ins.rule_handle}/version/{ins.version}",
                tenant_id=ins.namespace,
                status=200,
                payload=it.model_dump(),
            )
            out.append(
                {
                    "rule_handle": ins.rule_handle,
                    "version": ins.version,
                }
            )
        return {"ok": True, "created": out, "count": len(out)}

    @app.post(
        "/rules/validate",
        tags=["workbench", "rules"],
    )
    def validate_drl(b: RuleValidateRequest) -> dict[str, object]:
        try:
            parse(b.drl)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, str(e)) from e
        return {"ok": True, "message": "parse ok"}

    @app.get("/audit/logs", tags=["governance"])
    def audit_logs(
        req: Request,
        tenant_id: str | None = Query(None, description="Optional tenant filter"),
    ) -> list[dict[str, object]]:
        p = principal_from_request(req)
        require_any_role(p, {"platform_admin"})
        sid = d.audit_log.current_snapshot_id()
        rows = d.audit_log.snapshot(sid)
        if tenant_id:
            rows = [x for x in rows if x.get("tenant_id") == tenant_id]
        return rows

    @app.get("/lineage/events", tags=["governance"])
    def lineage_events(req: Request, run_id: str | None = Query(None)) -> list[dict[str, object]]:
        p = principal_from_request(req)
        require_any_role(p, {"platform_admin"})
        rows = [
            {
                "event_type": e.event_type,
                "run_id": e.run_id,
                "ts": e.ts,
                "payload": dict(e.payload),
            }
            for e in d.lineage.events
        ]
        if run_id:
            rows = [x for x in rows if x["run_id"] == run_id]
        return rows

    @app.get(
        "/system/deployment",
        response_model=DeploymentStatusResponse,
        tags=["workbench", "system"],
    )
    def deployment_status() -> DeploymentStatusResponse:
        return DeploymentStatusResponse(
            status="ok",
            engine_config=runtime_conf(EngineConfig()),
        )

    @app.get("/workbench/api/guided-fields", tags=["workbench"])
    def workbench_guided_fields(
        pattern: str = (
            'rule {rule_name} when $t : T ( $t.x > {min_x} ) then end'
        ),
    ) -> dict[str, object]:
        t = RuleTemplate.from_pattern("workbench", pattern)
        fields = guided_fields_from_template(t)
        return {
            "pattern": pattern,
            "fields": [
                GuidedFieldItem(
                    name=f.name, label=f.label, required=f.required, kind=f.kind
                )
                for f in fields
            ],
        }

    @app.post(
        "/dq/evaluate",
        response_model=DqEvaluateResponse,
        tags=["dq"],
    )
    def dq_evaluate(request: Request, req: DqEvaluateRequest) -> DqEvaluateResponse:
        p = principal_from_request(request)
        require_any_role(p, {"dq_steward", "rule_admin", "platform_admin"})
        _lineage_start(
            req.run_id,
            inputs={"fact": dict(req.fact)},
            context={"mode": "DQ", "endpoint": "/dq/evaluate"},
        )
        try:
            checks = checks_from_api(
                [x.model_dump() for x in req.checks]
            )
        except Exception as e:  # noqa: BLE001
            _lineage_fail(req.run_id, exc=e)
            raise HTTPException(400, str(e)) from e
        v = d.dq.evaluate(dict(req.fact), checks, rows=req.rows)
        s = summarize_violations(v)
        out = [
            DqViolationResponse(
                code=x.code,
                field=x.field,
                message=x.message,
                severity=x.severity.value,
                scope=x.scope.value,
            )
            for x in v
        ]
        dq_snapshot_id: int | None = None
        dq_quarantine_snapshot_id: int | None = None
        if req.persist and out:
            recs = to_violation_records(
                run_id=req.run_id,
                fact_id=req.fact_id,
                rule_set_version=req.rule_set_version,
                config_fingerprint=req.config_fingerprint,
                items=v,
            )
            dq_snapshot_id = d.dq_violations.append(
                [asdict(x) for x in recs]
            )
            _audit(
                request,
                action="dq_evaluate_persist",
                resource="/dq/evaluate",
                tenant_id=p.tenant_id,
                status=200,
                payload=req.model_dump(),
            )
            criticals = [x for x in v if x.severity.value == "CRITICAL"]
            if criticals:
                dq_quarantine_snapshot_id = d.dq_quarantine.append(
                    [
                        {
                            "run_id": req.run_id,
                            "fact_id": req.fact_id,
                            "rule_set_version": req.rule_set_version,
                            "config_fingerprint": req.config_fingerprint,
                            "fact_json": json.dumps(req.fact, sort_keys=True),
                            "critical_codes": ",".join(x.code for x in criticals),
                        }
                    ]
                )
        _lineage_complete(
            req.run_id,
            outputs={
                "violations_total": len(out),
                "dq_snapshot_id": dq_snapshot_id,
                "dq_quarantine_snapshot_id": dq_quarantine_snapshot_id,
            },
            metrics={
                "facts_processed": 1 if req.rows is None else len(req.rows),
                "violations_by_severity": {
                    "info": s["info_count"],
                    "warn": s["warn_count"],
                    "error": s["error_count"],
                    "critical": s["critical_count"],
                },
            },
        )
        return DqEvaluateResponse(
            ok=not out,
            violations=out,
            info_count=s["info_count"],
            warn_count=s["warn_count"],
            error_count=s["error_count"],
            critical_count=s["critical_count"],
            total=s["total"],
            run_id=req.run_id,
            dq_snapshot_id=dq_snapshot_id,
            dq_quarantine_snapshot_id=dq_quarantine_snapshot_id,
        )

    @app.get("/governance/environments", tags=["governance"])
    def governance_environments() -> list[str]:
        return list(STANDARD_ENVS)

    @app.get("/governance/namespaces", tags=["governance"])
    def governance_namespaces(req: Request) -> list[str]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_reader", "rule_author", "rule_admin", "platform_admin"})
        if "platform_admin" in p.roles:
            return sorted({r.namespace for r in d.store.list(None)})
        return [p.tenant_id]

    @app.get(
        "/governance/pins",
        tags=["governance"],
    )
    def governance_pins(
        req: Request,
        namespace: str | None = Query(
            None, description="Optional filter by namespace"
        ),
    ) -> list[dict[str, object]]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_reader", "rule_author", "rule_admin", "platform_admin"})
        if namespace:
            require_tenant_match(p, namespace)
        elif "platform_admin" not in p.roles:
            namespace = p.tenant_id
        return d.promotion.all_pins(namespace)

    @app.post(
        "/governance/sync-dev",
        tags=["governance"],
    )
    def governance_sync_dev(
        req: Request,
        b: GovernanceSyncRequest,
    ) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        try:
            v = sync_dev_from_active(
                d.store, d.promotion, b.namespace, b.rule_handle
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        _audit(
            req,
            action="governance_sync_dev",
            resource=f"/governance/sync-dev/{b.rule_handle}",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return {
            "ok": True,
            "version": v,
            "environment": "dev",
        }

    @app.post(
        "/governance/promote",
        tags=["governance"],
    )
    def governance_promote(
        req: Request,
        b: GovernancePromoteRequest,
    ) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        v0 = d.promotion.get_pin(
            b.namespace, b.rule_handle, b.from_env
        )
        if v0 is None:
            raise HTTPException(
                400, "source pin is not set; sync dev first"
            )
        try:
            validate_version_namespace(
                d.store, b.namespace, b.rule_handle, v0
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        try:
            v1 = d.promotion.promote(
                b.namespace, b.rule_handle, b.from_env, b.to_env
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        _audit(
            req,
            action="governance_promote",
            resource=f"/governance/promote/{b.rule_handle}",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return {
            "ok": True,
            "version": v1,
            "environment": b.to_env,
        }

    install_optional_api_key_middleware(app)

    static_dir = Path(__file__).resolve().parent / "static" / "workbench"
    app.mount(
        "/workbench",
        StaticFiles(directory=str(static_dir), html=True),
        name="workbench",
    )

    return app

