from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    rule_handle: str
    group: str = "default"
    namespace: str = "default"
    drl: str = Field(..., min_length=1)


class RuleResponse(BaseModel):
    rule_handle: str
    version: int


class RuleVersionActivePatchRequest(BaseModel):
    is_active: bool


class RuleVersionActiveResponse(BaseModel):
    rule_handle: str
    version: int
    is_active: bool


class SimulationRequest(BaseModel):
    drl: str
    fact: dict[str, Any]


class SimulationResponse(BaseModel):
    fired: bool
    action: dict[str, object] = {}
    bound: dict[str, object] = {}


class ChainStepResponse(BaseModel):
    rule_name: str
    fired: bool
    skipped: bool
    skip_reason: str | None = None
    action_output: dict[str, object] = {}
    stop_on_fire: bool = False


class SimulationChainRequest(BaseModel):
    """Multi-rule DRL (repeat `rule ... end` blocks). Phase 2k chain execution."""

    drl: str
    fact: dict[str, Any] = {}
    stop_on_decline: bool | None = None
    agenda_group_modes: dict[str, str] = {}


class SimulationChainResponse(BaseModel):
    any_fired: bool
    last_fired: bool
    final_action: dict[str, object] = {}
    final_bound: dict[str, object] = {}
    steps: list[ChainStepResponse] = []
    stop_reason: str | None = None


class DqCheckRequest(BaseModel):
    kind: str
    field: str
    severity: str = "ERROR"
    scope: str = "FIELD"
    code: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    min_count: int | None = None
    max_count: int | None = None
    other_field: str | None = None
    pattern: str | None = None
    max_age_seconds: int | None = None
    tolerance: float | None = None
    inclusive: bool = True
    allowed_values: list[Any] | None = None


class DqEvaluateRequest(BaseModel):
    fact: dict[str, Any]
    rows: list[dict[str, Any]] | None = None
    checks: list[DqCheckRequest]
    run_id: str = "run-local"
    fact_id: str = "fact-0"
    rule_set_version: str = "phase2a"
    config_fingerprint: str = "default"
    persist: bool = False


class DqViolationResponse(BaseModel):
    code: str
    field: str
    message: str
    severity: str
    scope: str


class DqEvaluateResponse(BaseModel):
    ok: bool
    violations: list[DqViolationResponse]
    info_count: int = 0
    warn_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    total: int = 0
    run_id: str = ""
    dq_snapshot_id: int | None = None
    dq_quarantine_snapshot_id: int | None = None


class RunSubmissionRequest(BaseModel):
    table_name: str
    drl: str = ""


class RuleAssetResponse(BaseModel):
    rule_handle: str
    version: int
    rule_group: str
    namespace: str = "default"
    salience: int
    is_active: bool
    drl: str


class DeploymentStatusResponse(BaseModel):
    status: str
    service: str = "sparkrules-api"
    engine_config: dict[str, str]
    platforms_supported: list[str] = Field(
        default_factory=lambda: [
            "local",
            "glue",
            "databricks",
            "gcp-dataproc",
            "azure-synapse",
        ]
    )


class GuidedFieldItem(BaseModel):
    name: str
    label: str
    required: bool
    kind: str


class RuleValidateRequest(BaseModel):
    drl: str = Field(..., min_length=1)


class RuleVersionDiffResponse(BaseModel):
    rule_handle: str
    version_a: int
    version_b: int
    drl_a: str
    drl_b: str
    unified_diff: str


class RuleImportRequest(BaseModel):
    items: list[RuleCreateRequest] = Field(..., min_length=1)


class GovernanceSyncRequest(BaseModel):
    namespace: str = "default"
    rule_handle: str = Field(..., min_length=1)


class GovernancePromoteRequest(BaseModel):
    namespace: str = "default"
    rule_handle: str = Field(..., min_length=1)
    from_env: str
    to_env: str


class AiSuggestRulesRequest(BaseModel):
    namespace: str = "default"
    rule_handle: str = "candidate"
    facts: list[dict[str, Any]] = []


class AiSuggestionResponse(BaseModel):
    id: str
    kind: str
    namespace: str
    rule_handle: str
    drl: str
    is_active: bool
    source: str
    status: str
    simulator_result: dict[str, Any] | None = None
    model_id: str


class AiMineDqRequest(BaseModel):
    field: str
    namespace: str = "default"
    facts: list[dict[str, Any]] = []


class AiAnalyzeDriftRequest(BaseModel):
    namespace: str = "default"
    handle: str
    history: list[float] = []


class AiExplainRuleRequest(BaseModel):
    drl: str


class AiExplainRuleResponse(BaseModel):
    explanation: str
