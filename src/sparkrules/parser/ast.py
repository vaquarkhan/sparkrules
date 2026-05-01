from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Union

Expr = Union[
    "BinaryOp", "Not", "Identifier", "Literal", "ListExpr", "InExpr", "CallExpr", "FieldAccess"
]


class BinaryOperator(Enum):
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    AND = "and"
    OR = "or"
    IN = "in"
    NOT_IN = "not in"
    CONTAINS = "contains"
    MATCHES = "matches"


@dataclass(frozen=True, slots=True)
class Literal:
    value: Any


@dataclass(frozen=True, slots=True)
class Identifier:
    name: str

    @property
    def base(self) -> str:
        if "." in self.name:
            return self.name.split(".", 1)[0]
        return self.name


@dataclass(frozen=True, slots=True)
class ListExpr:
    items: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class InExpr:
    left: Expr
    right: Expr
    negated: bool


@dataclass(frozen=True, slots=True)
class CallExpr:
    name: str
    args: tuple[Expr, ...]


@dataclass(frozen=True, slots=True)
class FieldAccess:
    base: str
    field: str


@dataclass(frozen=True, slots=True)
class BinaryOp:
    op: BinaryOperator
    left: Expr
    right: Expr


@dataclass(frozen=True, slots=True)
class Not:
    expr: Expr


@dataclass(frozen=True, slots=True)
class FactPattern:
    bind_name: str
    fact_type: str
    constraint: Expr | None


@dataclass(frozen=True, slots=True)
class Action:
    field_path: str
    expr: Expr


@dataclass(frozen=True, slots=True)
class RuleAst:
    name: str
    salience: int
    agenda_group: str
    activation_group: str | None
    pass_name: str | None
    group_by: tuple[str, ...]
    reason_codes: tuple[str, ...]
    stop_on_fire: bool
    when: tuple[FactPattern, ...]
    then: tuple[Action, ...]


class ParseError(ValueError):
    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        super().__init__(message)
        self.line = line
        self.col = col
