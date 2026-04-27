from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
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
    SimulationRequest,
    SimulationResponse,
)
from sre.api.security import install_optional_api_key_middleware
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
    promotion: PromotionRegistry = field(default_factory=PromotionRegistry)


def create_app(deps: AppDeps | None = None) -> Any:
    d = deps or AppDeps()
    app = FastAPI(title="sparkrules", version="0.1.0")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/rules", tags=["rules"])
    def list_rules() -> list[str]:
        return sorted(
            {r.rule_handle for r in d.store.list(None)}
        )

    @app.post(
        "/rules", tags=["rules"], response_model=RuleResponse
    )
    def post_rule(
        b: RuleCreateRequest,
    ) -> RuleResponse:
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
        return RuleResponse(
            rule_handle=ins.rule_handle, version=ins.version
        )

    @app.post(
        "/simulations",
        response_model=SimulationResponse,
        tags=["simulation"],
    )
    def sim(s: SimulationRequest) -> SimulationResponse:
        f = d.sim.run(s.drl, dict(s.fact))
        return SimulationResponse(
            fired=f.fired, action=f.action, bound=f.bound
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
        q: str | None = Query(None, description="Filter: substring on handle or DRL"),
        group: str | None = Query(
            None, description="Filter: exact rule_group"
        ),
        namespace: str | None = Query(
            None, description="Filter: exact namespace (Phase 4 governance)"
        ),
    ) -> list[RuleAssetResponse]:
        f: RuleFilter | None = None
        if namespace is not None and namespace != "":
            f = RuleFilter(namespace=namespace)
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
        rule_handle: str,
        version: int,
        b: RuleVersionActivePatchRequest,
    ) -> RuleVersionActiveResponse:
        try:
            r = d.store.get(rule_handle, version)
        except UnknownRuleError as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
        try:
            new = d.store.update(
                rule_handle, r.with_updates(is_active=b.is_active)
            )
        except ConflictError as e:  # noqa: BLE001
            raise HTTPException(409, str(e)) from e
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
    def import_rule_pack(b: RuleImportRequest) -> dict[str, Any]:
        out: list[dict[str, object]] = []
        for it in b.items:
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
    def dq_evaluate(req: DqEvaluateRequest) -> DqEvaluateResponse:
        try:
            checks = checks_from_api(
                [x.model_dump() for x in req.checks]
            )
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, str(e)) from e
        v = d.dq.evaluate(dict(req.fact), checks)
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
        return DqEvaluateResponse(
            ok=not out,
            violations=out,
            warn_count=s["warn_count"],
            error_count=s["error_count"],
            total=s["total"],
            run_id=req.run_id,
            dq_snapshot_id=dq_snapshot_id,
        )

    @app.get("/governance/environments", tags=["governance"])
    def governance_environments() -> list[str]:
        return list(STANDARD_ENVS)

    @app.get("/governance/namespaces", tags=["governance"])
    def governance_namespaces() -> list[str]:
        return sorted({r.namespace for r in d.store.list(None)})

    @app.get(
        "/governance/pins",
        tags=["governance"],
    )
    def governance_pins(
        namespace: str | None = Query(
            None, description="Optional filter by namespace"
        ),
    ) -> list[dict[str, object]]:
        return d.promotion.all_pins(namespace)

    @app.post(
        "/governance/sync-dev",
        tags=["governance"],
    )
    def governance_sync_dev(
        b: GovernanceSyncRequest,
    ) -> dict[str, object]:
        try:
            v = sync_dev_from_active(
                d.store, d.promotion, b.namespace, b.rule_handle
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
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
        b: GovernancePromoteRequest,
    ) -> dict[str, object]:
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

