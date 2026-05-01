from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import hashlib
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from sparkrules.api.rulepack import build_export_payload, unified_diff_drl
from sparkrules.api.schemas import (
    DeploymentStatusResponse,
    DqEvaluateRequest,
    DqEvaluateResponse,
    DqViolationResponse,
    DeprecationApproveRequest,
    DeprecationEnforceRequest,
    DeprecationEnforceResponse,
    DeprecationProposeRequest,
    DeprecationRecordResponse,
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
    BatchSimulationRequest,
    BatchSimulationResponse,
    BatchSimulationResultItem,
    ShadowSimulationRequest,
    ShadowSimulationResponse,
    CoverageSimulationRequest,
    CoverageSimulationResponse,
    CounterfactualSimulationRequest,
    CounterfactualSimulationResponse,
    RuleCoverageItemResponse,
    TimeTravelCaptureRequest,
    TimeTravelCaptureResponse,
    TimeTravelReplayRequest,
    TimeTravelReplayResponse,
    AiSuggestRulesRequest,
    AiSuggestionResponse,
    AiSuggestionSimulateRequest,
    AiMineDqRequest,
    AiAnalyzeDriftRequest,
    AiExplainRuleRequest,
    AiExplainRuleResponse,
    GraphEnrichRequest,
    GraphEnrichResponse,
    LspAnalyzeRequest,
    LspAnalyzeResponse,
    LspDiagnosticResponse,
    ModelScoreRequest,
    ModelScoreResponse,
)
from sparkrules.ai import AiService, StubAiProvider
from sparkrules.api.security import (
    install_optional_api_key_middleware,
    principal_from_request,
    require_any_role,
    require_tenant_match,
)
from sparkrules.dq import DataQualityEngine
from sparkrules.governance import DeprecationRegistry, PromotionRegistry, STANDARD_ENVS
from sparkrules.governance.promote_ops import (
    sync_dev_from_active,
    validate_version_namespace,
)
from sparkrules.dq.engine import checks_from_api, summarize_violations, to_violation_records
from sparkrules.model.rule import new_rule_id, Rule, RuleDefinition, RuleFormat
from sparkrules.model.rule_template import RuleTemplate
from sparkrules.ide import analyze_drl_for_lsp
from sparkrules.compiler import RuleEvaluationError
from sparkrules.parser import parse
from sparkrules.parser.ast import ParseError
from sparkrules.runtime import EngineConfig, guided_fields_from_template, runtime_conf
from sparkrules.runtime.lineage import InMemoryLineageSink, make_lineage_event
from sparkrules.runtime.graph import GraphEnricher, InMemoryGraphSource
from sparkrules.runtime.model import StubModelProvider, invoke_model
from sparkrules.runtime.iceberg_store import IcebergLikeTable
from sparkrules.sim import RuleSimulator
from sparkrules.store import (
    ConflictError,
    InMemoryRuleMetadataStore,
    RuleFilter,
    UnknownRuleError,
)


@dataclass
class AppDeps:
    store: InMemoryRuleMetadataStore = field(default_factory=InMemoryRuleMetadataStore)
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
            append_only=True,
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
            append_only=True,
        )
    )
    promotion: PromotionRegistry = field(default_factory=PromotionRegistry)
    deprecation: DeprecationRegistry = field(default_factory=DeprecationRegistry)
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
            append_only=True,
        )
    )
    ai: AiService = field(default_factory=lambda: AiService(StubAiProvider()))
    graph_source: InMemoryGraphSource = field(default_factory=InMemoryGraphSource)
    model_provider: StubModelProvider = field(default_factory=StubModelProvider)
    run_history: IcebergLikeTable = field(
        default_factory=lambda: IcebergLikeTable(
            "run_history",
            {
                "run_id": str,
                "model_id": str,
                "model_version": str,
                "provider": str,
                "features_json": str,
                "score": float,
            },
            append_only=True,
        )
    )
    model_pin: dict[str, str] = field(default_factory=dict)
    debug_runs: IcebergLikeTable = field(
        default_factory=lambda: IcebergLikeTable(
            "debug_runs",
            {
                "run_id": str,
                "drl": str,
                "fact_json": str,
                "ts": str,
            },
            append_only=True,
        )
    )


def create_app(deps: AppDeps | None = None) -> Any:
    d = deps or AppDeps()
    app = FastAPI(title="sparkrules", version="0.1.0")

    @app.exception_handler(RuleEvaluationError)
    def _rule_eval_err(_request: Request, exc: RuleEvaluationError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=400,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    def _hash_request_payload(payload: object) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _http_drl_parse_error(exc: Exception) -> HTTPException:
        return HTTPException(
            status_code=422,
            detail={"code": "DRL_PARSE_ERROR", "message": str(exc)},
        )

    def _http_bad_request(message: str, *, code: str = "BAD_REQUEST") -> HTTPException:
        return HTTPException(
            status_code=400,
            detail={"code": code, "message": message},
        )

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

    def _lineage_start(
        run_id: str, *, inputs: dict[str, object], context: dict[str, object]
    ) -> None:
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

    def _lineage_fail(
        run_id: str,
        *,
        exc: Exception,
        inputs: dict[str, object] | None = None,
        context: dict[str, object] | None = None,
        principal: str | None = None,
    ) -> None:
        pl: dict[str, object] = {
            "error_class": type(exc).__name__,
            "error_message": str(exc),
        }
        if inputs is not None:
            pl["inputs"] = inputs
        if context is not None:
            pl["context"] = context
        if principal is not None:
            pl["principal"] = principal
        d.lineage.emit(
            make_lineage_event("FAIL", run_id, payload=pl),
        )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/rules", tags=["rules"])
    def list_rules(req: Request) -> list[str]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        rows = d.store.list(None)
        if "platform_admin" not in p.roles:
            rows = [r for r in rows if r.namespace == p.tenant_id]
        return sorted({r.rule_handle for r in rows})

    @app.post("/rules", tags=["rules"], response_model=RuleResponse)
    def post_rule(
        req: Request,
        b: RuleCreateRequest,
    ) -> RuleResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_author", "rule_admin"})
        require_tenant_match(p, b.namespace)
        try:
            parse(b.drl)
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
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
            rule_definition=RuleDefinition(b.drl, RuleFormat.DRL),
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
        return RuleResponse(rule_handle=ins.rule_handle, version=ins.version)

    @app.post(
        "/simulations",
        response_model=SimulationResponse,
        tags=["simulation"],
    )
    def sim(req: Request, s: SimulationRequest) -> SimulationResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        run_id = f"sim-{uuid.uuid4()}"
        sim_inputs: dict[str, object] = {"fact": dict(s.fact)}
        sim_ctx = {"mode": "SIMULATION", "endpoint": "/simulations"}
        _lineage_start(run_id, inputs=sim_inputs, context=sim_ctx)
        try:
            f = d.sim.run(s.drl, dict(s.fact))
        except (ParseError, ValueError) as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=sim_inputs,
                context=sim_ctx,
                principal=p.principal,
            )
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=sim_inputs,
                context=sim_ctx,
                principal=p.principal,
            )
            raise
        except Exception as e:  # noqa: BLE001
            _lineage_fail(
                run_id,
                exc=e,
                inputs=sim_inputs,
                context=sim_ctx,
                principal=p.principal,
            )
            raise _http_bad_request(str(e), code="SIMULATION_FAILED") from e
        _lineage_complete(
            run_id,
            outputs={"fired": bool(f.fired)},
            metrics={"facts_processed": 1, "rules_fired": 1 if f.fired else 0},
        )
        return SimulationResponse(fired=f.fired, action=f.action, bound=f.bound)

    @app.post(
        "/simulations/batch",
        response_model=BatchSimulationResponse,
        tags=["simulation"],
    )
    def sim_batch(req: Request, s: BatchSimulationRequest) -> BatchSimulationResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        results: list[BatchSimulationResultItem] = []
        fired_count = 0
        for i, fact in enumerate(s.facts):
            try:
                f = d.sim.run(s.drl, dict(fact))
                if f.fired:
                    fired_count += 1
                results.append(
                    BatchSimulationResultItem(
                        index=i, fired=f.fired, action=f.action, bound=f.bound
                    )
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    BatchSimulationResultItem(
                        index=i, fired=False, error=str(e)
                    )
                )
        return BatchSimulationResponse(
            total=len(s.facts), fired_count=fired_count, results=results
        )

    @app.post(
        "/simulations/shadow",
        response_model=ShadowSimulationResponse,
        tags=["simulation"],
    )
    def sim_shadow(req: Request, s: ShadowSimulationRequest) -> ShadowSimulationResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        sh_inputs: dict[str, object] = {"fact": dict(s.fact)}
        sh_ctx = {"mode": "SIMULATION_SHADOW", "endpoint": "/simulations/shadow"}
        _lineage_start(s.run_id, inputs=sh_inputs, context=sh_ctx)
        try:
            out = d.sim.run_shadow(s.primary_drl, s.shadow_drl, dict(s.fact))
        except (ParseError, ValueError) as e:
            _lineage_fail(
                s.run_id,
                exc=e,
                inputs=sh_inputs,
                context=sh_ctx,
                principal=p.principal,
            )
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError as e:
            _lineage_fail(
                s.run_id,
                exc=e,
                inputs=sh_inputs,
                context=sh_ctx,
                principal=p.principal,
            )
            raise
        except Exception as e:  # noqa: BLE001
            _lineage_fail(
                s.run_id,
                exc=e,
                inputs=sh_inputs,
                context=sh_ctx,
                principal=p.principal,
            )
            raise _http_bad_request(str(e), code="SIMULATION_FAILED") from e
        _lineage_complete(
            s.run_id,
            outputs={"drifted": out.drifted, "drift_fields": list(out.drift_fields)},
            metrics={"facts_processed": 1, "primary_fired": 1 if out.primary.fired else 0},
        )
        return ShadowSimulationResponse(
            primary_fired=out.primary.fired,
            primary_action=out.primary.action,
            shadow_fired=out.shadow.fired,
            shadow_action=out.shadow.action,
            drifted=out.drifted,
            drift_fields=list(out.drift_fields),
        )

    @app.post(
        "/simulations/coverage",
        response_model=CoverageSimulationResponse,
        tags=["simulation"],
    )
    def sim_coverage(req: Request, s: CoverageSimulationRequest) -> CoverageSimulationResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        try:
            out = d.sim.analyze_coverage(s.drl, list(s.facts))
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise _http_bad_request(str(e), code="SIMULATION_FAILED") from e
        return CoverageSimulationResponse(
            total_facts=out.total_facts,
            total_rules=out.total_rules,
            covered_rules=out.covered_rules,
            items=[
                RuleCoverageItemResponse(
                    rule_name=i.rule_name,
                    fired_count=i.fired_count,
                    total=i.total,
                    fire_rate=i.fire_rate,
                )
                for i in out.items
            ],
        )

    @app.post(
        "/simulations/counterfactual",
        response_model=CounterfactualSimulationResponse,
        tags=["simulation"],
    )
    def sim_counterfactual(
        req: Request,
        s: CounterfactualSimulationRequest,
    ) -> CounterfactualSimulationResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        run_id = f"sim-cf-{uuid.uuid4()}"
        cf_inputs: dict[str, object] = {
            "baseline_fact": dict(s.baseline_fact),
            "candidate_fact": dict(s.candidate_fact),
        }
        cf_ctx = {
            "mode": "SIMULATION_COUNTERFACTUAL",
            "endpoint": "/simulations/counterfactual",
        }
        _lineage_start(run_id, inputs=cf_inputs, context=cf_ctx)
        try:
            b = d.sim.run(s.drl, dict(s.baseline_fact))
            c = d.sim.run(s.drl, dict(s.candidate_fact))
        except (ParseError, ValueError) as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=cf_inputs,
                context=cf_ctx,
                principal=p.principal,
            )
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=cf_inputs,
                context=cf_ctx,
                principal=p.principal,
            )
            raise
        except Exception as e:  # noqa: BLE001
            _lineage_fail(
                run_id,
                exc=e,
                inputs=cf_inputs,
                context=cf_ctx,
                principal=p.principal,
            )
            raise _http_bad_request(str(e), code="SIMULATION_FAILED") from e
        keys = set(b.action) | set(c.action)
        drift_fields = sorted(k for k in keys if b.action.get(k) != c.action.get(k))
        _lineage_complete(
            run_id,
            outputs={
                "baseline_fired": b.fired,
                "candidate_fired": c.fired,
                "drifted": bool(drift_fields),
            },
            metrics={
                "facts_processed": 2,
                "drift_field_count": len(drift_fields),
            },
        )
        return CounterfactualSimulationResponse(
            baseline_fired=b.fired,
            baseline_action=b.action,
            candidate_fired=c.fired,
            candidate_action=c.action,
            drifted=bool(drift_fields),
            drift_fields=drift_fields,
        )

    @app.post(
        "/debug/time-travel/capture",
        response_model=TimeTravelCaptureResponse,
        tags=["debug"],
    )
    def debug_time_travel_capture(
        req: Request,
        s: TimeTravelCaptureRequest,
    ) -> TimeTravelCaptureResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {"rule_author", "rule_admin", "run_operator", "platform_admin"},
        )
        try:
            r = d.sim.run(s.drl, dict(s.fact))
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise _http_bad_request(str(e), code="TIME_TRAVEL_FAILED") from e
        sid = d.debug_runs.append(
            [
                {
                    "run_id": s.run_id,
                    "drl": s.drl,
                    "fact_json": json.dumps(s.fact, sort_keys=True, default=str),
                    "ts": datetime.now(UTC).isoformat(),
                }
            ]
        )
        return TimeTravelCaptureResponse(
            run_id=s.run_id,
            snapshot_id=sid,
            fired=r.fired,
            action=r.action,
            bound=r.bound,
        )

    @app.post(
        "/debug/time-travel/replay",
        response_model=TimeTravelReplayResponse,
        tags=["debug"],
    )
    def debug_time_travel_replay(
        req: Request,
        s: TimeTravelReplayRequest,
    ) -> TimeTravelReplayResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {"rule_author", "rule_admin", "run_operator", "platform_admin"},
        )
        rows = d.debug_runs.snapshot(s.snapshot_id)
        row = next((x for x in rows if x.get("run_id") == s.run_id), None)
        if row is None:
            raise HTTPException(404, "run not found in snapshot")
        fact = (
            dict(s.fact_override)
            if s.fact_override is not None
            else json.loads(str(row["fact_json"]))
        )
        try:
            r = d.sim.run(str(row["drl"]), fact)
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise _http_bad_request(str(e), code="TIME_TRAVEL_FAILED") from e
        return TimeTravelReplayResponse(
            run_id=s.run_id,
            snapshot_id=s.snapshot_id,
            fired=r.fired,
            action=r.action,
            bound=r.bound,
            used_fact_override=s.fact_override is not None,
        )

    @app.post(
        "/simulations/chain",
        response_model=SimulationChainResponse,
        tags=["simulation"],
    )
    def sim_chain(
        req: Request,
        s: SimulationChainRequest,
    ) -> SimulationChainResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        run_id = f"sim-chain-{uuid.uuid4()}"
        ch_inputs: dict[str, object] = {"fact": dict(s.fact)}
        ch_ctx = {"mode": "SIMULATION_CHAIN", "endpoint": "/simulations/chain"}
        _lineage_start(run_id, inputs=ch_inputs, context=ch_ctx)
        sod = s.stop_on_decline if s.stop_on_decline is not None else d.engine_cfg.stop_on_decline
        try:
            cr = d.sim.run_chain(
                s.drl,
                dict(s.fact),
                stop_on_decline=sod,
                agenda_group_modes=dict(s.agenda_group_modes),
            )
        except (ParseError, ValueError) as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=ch_inputs,
                context=ch_ctx,
                principal=p.principal,
            )
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError as e:
            _lineage_fail(
                run_id,
                exc=e,
                inputs=ch_inputs,
                context=ch_ctx,
                principal=p.principal,
            )
            raise
        except Exception as e:  # noqa: BLE001
            _lineage_fail(
                run_id,
                exc=e,
                inputs=ch_inputs,
                context=ch_ctx,
                principal=p.principal,
            )
            raise _http_bad_request(str(e), code="SIMULATION_FAILED") from e
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
        require_any_role(
            p, {"rule_reader", "rule_author", "rule_admin", "ai_reviewer", "platform_admin"}
        )
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

    @app.post(
        "/ai/suggestions/{sid}/simulate",
        response_model=AiSuggestionResponse,
        tags=["ai"],
    )
    def ai_suggestion_simulate(
        req: Request,
        sid: str,
        b: AiSuggestionSimulateRequest,
    ) -> AiSuggestionResponse:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "platform_admin"})
        s = d.ai.store.get(sid)
        require_tenant_match(p, s.namespace)
        try:
            sim_out = d.sim.run(s.drl, dict(b.fact))
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
        except RuleEvaluationError:
            raise
        except Exception as e:  # noqa: BLE001
            raise _http_bad_request(str(e), code="AI_SIMULATION_FAILED") from e
        upd = d.ai.record_simulation_evidence(
            sid,
            fired=sim_out.fired,
            action=dict(sim_out.action),
            bound=dict(sim_out.bound),
        )
        _audit(
            req,
            action="ai_suggestion_simulate",
            resource=f"/ai/suggestions/{sid}/simulate",
            tenant_id=upd.namespace,
            status=200,
            payload={"sid": sid, "fired": sim_out.fired},
        )
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

    @app.post("/ai/suggestions/{sid}/approve", response_model=AiSuggestionResponse, tags=["ai"])
    def ai_approve(req: Request, sid: str) -> AiSuggestionResponse:
        p = principal_from_request(req)
        require_any_role(p, {"ai_reviewer", "platform_admin"})
        s = d.ai.store.get(sid)
        require_tenant_match(p, s.namespace)
        try:
            upd = d.ai.approve(sid)
        except ValueError as e:
            raise _http_bad_request(str(e), code="AI_APPROVE_FAILED") from e
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

    @app.post("/graph/enrich", response_model=GraphEnrichResponse, tags=["graph"])
    def graph_enrich(req: Request, b: GraphEnrichRequest) -> GraphEnrichResponse:
        p = principal_from_request(req)
        require_any_role(
            p, {"rule_reader", "rule_author", "rule_admin", "pii_reveal", "platform_admin"}
        )
        ge = GraphEnricher(
            source=d.graph_source,
            entity_field=b.entity_field,
            redacted_fields={"pii_node_id"},
            pii_reveal=bool(
                b.pii_reveal and ("pii_reveal" in p.roles or "platform_admin" in p.roles)
            ),
        )
        out = ge.enrich(dict(b.fact))
        return GraphEnrichResponse(snapshot_id=out.snapshot_id, fact=out.enriched_fact)

    @app.post("/models/score", response_model=ModelScoreResponse, tags=["model"])
    def model_score(req: Request, b: ModelScoreRequest) -> ModelScoreResponse:
        p = principal_from_request(req)
        require_any_role(p, {"run_operator", "rule_admin", "platform_admin"})
        mv = b.model_version
        if b.pin_current_version:
            if mv is None:
                mv = d.model_pin.get(b.model_id, "v1")
            d.model_pin[b.model_id] = mv
        else:
            mv = mv or "v1"
        inv = invoke_model(
            d.model_provider,
            model_id=b.model_id,
            model_version=mv,
            features=dict(b.features),
        )
        d.run_history.append(
            [
                {
                    "run_id": b.run_id,
                    "model_id": inv.model_id,
                    "model_version": inv.model_version,
                    "provider": inv.provider,
                    "features_json": json.dumps(inv.features, sort_keys=True, default=str),
                    "score": float(inv.score),
                }
            ]
        )
        _lineage_complete(
            b.run_id,
            outputs={"model_id": inv.model_id, "model_version": inv.model_version},
            metrics={"score": float(inv.score)},
        )
        return ModelScoreResponse(
            model_id=inv.model_id,
            model_version=inv.model_version,
            provider=inv.provider,
            score=inv.score,
            explanation=inv.explanation,
        )

    @app.get(
        "/rules/groups",
        tags=["workbench", "rules"],
    )
    def list_rule_groups(req: Request) -> list[str]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        rows = d.store.list(None)
        if "platform_admin" not in p.roles:
            rows = [r for r in rows if r.namespace == p.tenant_id]
        return sorted({r.rule_group for r in rows})

    @app.get(
        "/rules/assets",
        response_model=list[RuleAssetResponse],
        tags=["workbench", "rules"],
    )
    def list_rule_assets(
        req: Request,
        q: str | None = Query(None, description="Filter: substring on handle or DRL"),
        group: str | None = Query(None, description="Filter: exact rule_group"),
        namespace: str | None = Query(
            None, description="Filter: exact namespace (Phase 4 governance)"
        ),
    ) -> list[RuleAssetResponse]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
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
            out = [x for x in out if ql in x.rule_handle.lower() or ql in x.drl.lower()]
        if group is not None and group != "":
            out = [x for x in out if x.rule_group == group]
        return sorted(out, key=lambda x: (x.rule_handle, x.version))

    @app.get(
        "/rules/{rule_handle}/version/{version}",
        response_model=RuleAssetResponse,
        tags=["workbench", "rules"],
    )
    def get_rule_version(
        req: Request,
        rule_handle: str,
        version: int,
    ) -> RuleAssetResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        try:
            r = d.store.get(rule_handle, version)
        except UnknownRuleError as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
        require_tenant_match(p, r.namespace)
        return RuleAssetResponse(
            rule_handle=r.rule_handle,
            version=r.version,
            rule_group=r.rule_group,
            namespace=r.namespace,
            salience=r.salience,
            is_active=r.is_active,
            drl=r.rule_definition.source,
        )

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
            new = d.store.update(rule_handle, r.with_updates(is_active=b.is_active))
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
        req: Request,
        handle: str = Query(..., min_length=1),
        version_a: int = Query(..., ge=1),
        version_b: int = Query(..., ge=1),
    ) -> RuleVersionDiffResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        try:
            ra = d.store.get(handle, version_a)
            rb = d.store.get(handle, version_b)
        except UnknownRuleError as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
        require_tenant_match(p, ra.namespace)
        require_tenant_match(p, rb.namespace)
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
    def export_rule_pack(
        req: Request,
        namespace: str | None = Query(None, description="Optional filter by namespace"),
    ) -> dict[str, Any]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        if namespace:
            require_tenant_match(p, namespace)
            rows = d.store.list(RuleFilter(namespace=namespace))
        elif "platform_admin" in p.roles:
            rows = d.store.list(None)
        else:
            rows = d.store.list(RuleFilter(namespace=p.tenant_id))
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
            except (ParseError, ValueError) as e:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "DRL_PARSE_ERROR", "message": f"{it.rule_handle}: {e}"},
                ) from e
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
                rule_definition=RuleDefinition(it.drl, RuleFormat.DRL),
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
    def validate_drl(req: Request, b: RuleValidateRequest) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        try:
            parse(b.drl)
        except (ParseError, ValueError) as e:
            raise _http_drl_parse_error(e) from e
        return {"ok": True, "message": "parse ok"}

    @app.post(
        "/ide/lsp/analyze",
        response_model=LspAnalyzeResponse,
        tags=["workbench", "ide"],
    )
    def lsp_analyze(req: Request, b: LspAnalyzeRequest) -> LspAnalyzeResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        out = analyze_drl_for_lsp(b.drl, prefix=b.prefix)
        return LspAnalyzeResponse(
            diagnostics=[
                LspDiagnosticResponse(
                    severity=d.severity,
                    message=d.message,
                    line=d.line,
                    col=d.col,
                )
                for d in out.diagnostics
            ],
            completions=list(out.completions),
        )

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
    def deployment_status(req: Request) -> DeploymentStatusResponse:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        return DeploymentStatusResponse(
            status="ok",
            engine_config=runtime_conf(EngineConfig()),
        )

    @app.get("/workbench/api/guided-fields", tags=["workbench"])
    def workbench_guided_fields(
        req: Request,
        pattern: str = ("rule {rule_name} when $t : T ( $t.x > {min_x} ) then end"),
    ) -> dict[str, object]:
        p = principal_from_request(req)
        require_any_role(
            p,
            {
                "rule_reader",
                "rule_author",
                "rule_admin",
                "run_operator",
                "dq_steward",
                "ai_reviewer",
            },
        )
        t = RuleTemplate.from_pattern("workbench", pattern)
        fields = guided_fields_from_template(t)
        return {
            "pattern": pattern,
            "fields": [
                GuidedFieldItem(name=f.name, label=f.label, required=f.required, kind=f.kind)
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
        dq_ctx = {"mode": "DQ", "endpoint": "/dq/evaluate"}
        dq_in = {"fact": dict(req.fact)}
        try:
            checks = checks_from_api([x.model_dump() for x in req.checks])
        except Exception as e:  # noqa: BLE001
            _lineage_fail(
                req.run_id,
                exc=e,
                inputs=dq_in,
                context=dq_ctx,
                principal=p.principal,
            )
            raise _http_bad_request(str(e), code="DQ_EVALUATION_FAILED") from e
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
            dq_snapshot_id = d.dq_violations.append([asdict(x) for x in recs])
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
    def governance_environments(req: Request) -> list[str]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_reader", "rule_author", "rule_admin", "platform_admin"})
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
        namespace: str | None = Query(None, description="Optional filter by namespace"),
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
            v = sync_dev_from_active(d.store, d.promotion, b.namespace, b.rule_handle)
        except ValueError as e:
            raise _http_bad_request(str(e), code="GOVERNANCE_SYNC_FAILED") from e
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
        v0 = d.promotion.get_pin(b.namespace, b.rule_handle, b.from_env)
        if v0 is None:
            raise _http_bad_request(
                "source pin is not set; sync dev first",
                code="GOVERNANCE_PIN_MISSING",
            )
        try:
            validate_version_namespace(d.store, b.namespace, b.rule_handle, v0)
        except ValueError as e:
            raise _http_bad_request(str(e), code="GOVERNANCE_PROMOTE_FAILED") from e
        try:
            v1 = d.promotion.promote(b.namespace, b.rule_handle, b.from_env, b.to_env)
        except ValueError as e:
            raise _http_bad_request(str(e), code="GOVERNANCE_PROMOTE_FAILED") from e
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

    @app.post(
        "/governance/deprecations/propose",
        response_model=DeprecationRecordResponse,
        tags=["governance"],
    )
    def governance_deprecate_propose(
        req: Request,
        b: DeprecationProposeRequest,
    ) -> DeprecationRecordResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        r = d.deprecation.propose(
            namespace=b.namespace,
            rule_handle=b.rule_handle,
            requested_by=p.principal,
            reason=b.reason,
        )
        _audit(
            req,
            action="governance_deprecate_propose",
            resource=f"/governance/deprecations/propose/{b.rule_handle}",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return DeprecationRecordResponse(
            namespace=r.namespace,
            rule_handle=r.rule_handle,
            requested_by=r.requested_by,
            reason=r.reason,
            status=r.status,
            requested_at=r.requested_at,
            approved_by=r.approved_by,
            approved_at=r.approved_at,
        )

    @app.post(
        "/governance/deprecations/approve",
        response_model=DeprecationRecordResponse,
        tags=["governance"],
    )
    def governance_deprecate_approve(
        req: Request,
        b: DeprecationApproveRequest,
    ) -> DeprecationRecordResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        try:
            r = d.deprecation.approve(
                namespace=b.namespace,
                rule_handle=b.rule_handle,
                approved_by=p.principal,
            )
        except KeyError as e:
            raise HTTPException(404, "deprecation proposal not found") from e
        _audit(
            req,
            action="governance_deprecate_approve",
            resource=f"/governance/deprecations/approve/{b.rule_handle}",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return DeprecationRecordResponse(
            namespace=r.namespace,
            rule_handle=r.rule_handle,
            requested_by=r.requested_by,
            reason=r.reason,
            status=r.status,
            requested_at=r.requested_at,
            approved_by=r.approved_by,
            approved_at=r.approved_at,
        )

    @app.get(
        "/governance/deprecations",
        response_model=list[DeprecationRecordResponse],
        tags=["governance"],
    )
    def governance_deprecations(
        req: Request,
        namespace: str | None = Query(None, description="Optional filter by namespace"),
    ) -> list[DeprecationRecordResponse]:
        p = principal_from_request(req)
        require_any_role(p, {"rule_reader", "rule_author", "rule_admin", "platform_admin"})
        if namespace:
            require_tenant_match(p, namespace)
        elif "platform_admin" not in p.roles:
            namespace = p.tenant_id
        rows = d.deprecation.list(namespace=namespace)
        return [DeprecationRecordResponse(**x) for x in rows]

    @app.post(
        "/governance/deprecations/enforce",
        response_model=DeprecationEnforceResponse,
        tags=["governance"],
    )
    def governance_deprecations_enforce(
        req: Request,
        b: DeprecationEnforceRequest,
    ) -> DeprecationEnforceResponse:
        p = principal_from_request(req)
        require_any_role(p, {"rule_admin", "platform_admin"})
        require_tenant_match(p, b.namespace)
        rows = d.deprecation.list(namespace=b.namespace)
        if b.rule_handle:
            rows = [x for x in rows if x["rule_handle"] == b.rule_handle]
        approved = [x for x in rows if x.get("status") == "APPROVED"]
        enforced_rules = 0
        deactivated_versions = 0
        details: list[dict[str, object]] = []
        for r in approved:
            handle = str(r["rule_handle"])
            active = d.store.list(
                RuleFilter(namespace=b.namespace, rule_handle=handle, is_active=True)
            )
            if not active:
                continue
            enforced_rules += 1
            hit = 0
            for cur in active:
                d.store.update(cur.rule_handle, cur.with_updates(is_active=False))
                hit += 1
                deactivated_versions += 1
            details.append(
                {
                    "rule_handle": handle,
                    "deactivated_versions": hit,
                }
            )
        _audit(
            req,
            action="governance_deprecations_enforce",
            resource="/governance/deprecations/enforce",
            tenant_id=b.namespace,
            status=200,
            payload=b.model_dump(),
        )
        return DeprecationEnforceResponse(
            namespace=b.namespace,
            enforced_rules=enforced_rules,
            deactivated_versions=deactivated_versions,
            details=details,
        )

    install_optional_api_key_middleware(app)

    static_dir = Path(__file__).resolve().parent / "static" / "workbench"
    app.mount(
        "/workbench",
        StaticFiles(directory=str(static_dir), html=True),
        name="workbench",
    )

    return app
