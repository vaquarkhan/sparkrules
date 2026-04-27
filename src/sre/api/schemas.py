from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    rule_handle: str
    group: str = "default"
    drl: str = Field(..., min_length=1)


class RuleResponse(BaseModel):
    rule_handle: str
    version: int


class SimulationRequest(BaseModel):
    drl: str
    fact: dict[str, Any]


class SimulationResponse(BaseModel):
    fired: bool
    action: dict[str, object] = {}
    bound: dict[str, object] = {}


class DqCheckRequest(BaseModel):
    kind: str
    field: str
    severity: str = "ERROR"
    scope: str = "FIELD"
    code: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    inclusive: bool = True
    allowed_values: list[Any] | None = None


class DqEvaluateRequest(BaseModel):
    fact: dict[str, Any]
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
    warn_count: int = 0
    error_count: int = 0
    total: int = 0
    run_id: str = ""
    dq_snapshot_id: int | None = None


class RunSubmissionRequest(BaseModel):
    table_name: str
    drl: str = ""


class RuleAssetResponse(BaseModel):
    rule_handle: str
    version: int
    rule_group: str
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
