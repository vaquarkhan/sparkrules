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
    code: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    inclusive: bool = True
    allowed_values: list[Any] | None = None


class DqEvaluateRequest(BaseModel):
    fact: dict[str, Any]
    checks: list[DqCheckRequest]


class DqViolationResponse(BaseModel):
    code: str
    field: str
    message: str
    severity: str


class DqEvaluateResponse(BaseModel):
    ok: bool
    violations: list[DqViolationResponse]
    warn_count: int = 0
    error_count: int = 0
    total: int = 0


class RunSubmissionRequest(BaseModel):
    table_name: str
    drl: str = ""
