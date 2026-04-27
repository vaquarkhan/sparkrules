from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from starlette.staticfiles import StaticFiles

from sre.api.schemas import (
    DeploymentStatusResponse,
    DqEvaluateRequest,
    DqEvaluateResponse,
    DqViolationResponse,
    GuidedFieldItem,
    RuleAssetResponse,
    RuleCreateRequest,
    RuleResponse,
    RuleValidateRequest,
    SimulationRequest,
    SimulationResponse,
)
from sre.dq import DataQualityEngine
from sre.dq.engine import checks_from_api, summarize_violations, to_violation_records
from sre.model.rule import new_rule_id, Rule, RuleDefinition, RuleFormat
from sre.model.rule_template import RuleTemplate
from sre.parser import parse
from sre.runtime import EngineConfig, guided_fields_from_template, runtime_conf
from sre.runtime.iceberg_store import IcebergLikeTable
from sre.sim import RuleSimulator
from sre.store import InMemoryRuleMetadataStore


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
        "/rules/assets",
        response_model=list[RuleAssetResponse],
        tags=["workbench", "rules"],
    )
    def list_rule_assets() -> list[RuleAssetResponse]:
        rows = d.store.list(None)
        out = [
            RuleAssetResponse(
                rule_handle=r.rule_handle,
                version=r.version,
                rule_group=r.rule_group,
                salience=r.salience,
                is_active=r.is_active,
                drl=r.rule_definition.source,
            )
            for r in rows
        ]
        return sorted(out, key=lambda x: (x.rule_handle, x.version))

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

    static_dir = Path(__file__).resolve().parent / "static" / "workbench"
    app.mount(
        "/workbench",
        StaticFiles(directory=str(static_dir), html=True),
        name="workbench",
    )

    return app

