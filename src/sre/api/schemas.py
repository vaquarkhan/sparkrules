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


class RunSubmissionRequest(BaseModel):
    table_name: str
    drl: str = ""
