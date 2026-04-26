from __future__ import annotations

import hashlib
import dataclasses
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto
from typing import Any
from uuid import UUID, uuid4


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_rule_id() -> UUID:
    return uuid4()


class Pass(Enum):
    SINGLE = auto()
    PASS_1 = auto()
    PASS_2 = auto()


class RuleStatus(Enum):
    DRAFT = auto()
    ACTIVE = auto()
    INACTIVE = auto()


class RuleFormat(Enum):
    DRL = auto()
    DECISION_TABLE_JSON = auto()


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    source: str
    format: RuleFormat


DEFAULT_AGENDA_GROUP = "MAIN"


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: UUID
    rule_handle: str
    version: int
    rule_group: str
    salience: int
    effective_from: datetime
    effective_to: datetime | None
    is_active: bool
    rule_definition: RuleDefinition
    activation_group: str | None
    reason_codes: tuple[str, ...] = ()
    pass_: Pass = Pass.SINGLE
    group_by_keys: tuple[str, ...] = ()
    source_file_hash: str | None = None
    author_principal: str = "system"
    created_at: datetime = field(default_factory=now_utc)

    def with_updates(self, **kwargs: Any) -> Rule:
        return dataclasses.replace(self, **kwargs)


def active_set_hash(pairs: list[tuple[str, int]]) -> str:
    body = ",".join(f"{h}:{v}" for h, v in sorted(pairs))
    return hashlib.sha256(body.encode()).hexdigest()
