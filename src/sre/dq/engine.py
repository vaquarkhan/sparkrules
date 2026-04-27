from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence


class DqSeverity(str, Enum):
    WARN = "WARN"
    ERROR = "ERROR"


class DqScope(str, Enum):
    ROW = "ROW"
    FIELD = "FIELD"


@dataclass(frozen=True, slots=True)
class DqViolation:
    code: str
    field: str
    message: str
    severity: DqSeverity
    scope: DqScope = DqScope.ROW


@dataclass(frozen=True, slots=True)
class ExpectNotNull:
    field: str
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "not_null"
    scope: DqScope = DqScope.FIELD


@dataclass(frozen=True, slots=True)
class ExpectBetween:
    field: str
    min_value: float | int
    max_value: float | int
    inclusive: bool = True
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "between"
    scope: DqScope = DqScope.FIELD


@dataclass(frozen=True, slots=True)
class ExpectInSet:
    field: str
    allowed_values: tuple[Any, ...]
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "in_set"
    scope: DqScope = DqScope.FIELD


DqCheck = ExpectNotNull | ExpectBetween | ExpectInSet


@dataclass(frozen=True, slots=True)
class DqViolationRecord:
    run_id: str
    fact_id: str
    rule_set_version: str
    config_fingerprint: str
    code: str
    field: str
    message: str
    severity: str
    scope: str


class DataQualityEngine:
    def evaluate(
        self,
        fact: dict[str, Any],
        checks: Sequence[DqCheck],
    ) -> list[DqViolation]:
        out: list[DqViolation] = []
        for c in checks:
            if isinstance(c, ExpectNotNull):
                v = fact.get(c.field)
                if v is None:
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=f"{c.field!r} is null",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectBetween):
                raw = fact.get(c.field)
                if not isinstance(raw, (int, float)):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=f"{c.field!r} is not numeric",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                    continue
                ok = (
                    c.min_value <= raw <= c.max_value
                    if c.inclusive
                    else c.min_value < raw < c.max_value
                )
                if not ok:
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=(
                                f"{c.field!r}={raw} is outside [{c.min_value}, {c.max_value}]"
                                if c.inclusive
                                else f"{c.field!r}={raw} is outside ({c.min_value}, {c.max_value})"
                            ),
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectInSet):
                raw = fact.get(c.field)
                if raw not in c.allowed_values:
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=(
                                f"{c.field!r}={raw!r} is not in {list(c.allowed_values)!r}"
                            ),
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            raise TypeError(type(c).__name__)
        return out


def summarize_violations(items: Sequence[DqViolation]) -> dict[str, int]:
    warn_count = sum(1 for x in items if x.severity == DqSeverity.WARN)
    error_count = sum(1 for x in items if x.severity == DqSeverity.ERROR)
    return {
        "warn_count": warn_count,
        "error_count": error_count,
        "total": warn_count + error_count,
    }


def to_violation_records(
    run_id: str,
    fact_id: str,
    rule_set_version: str,
    config_fingerprint: str,
    items: Sequence[DqViolation],
) -> list[DqViolationRecord]:
    return [
        DqViolationRecord(
            run_id=run_id,
            fact_id=fact_id,
            rule_set_version=rule_set_version,
            config_fingerprint=config_fingerprint,
            code=x.code,
            field=x.field,
            message=x.message,
            severity=x.severity.value,
            scope=x.scope.value,
        )
        for x in items
    ]


def checks_from_api(items: Iterable[dict[str, Any]]) -> list[DqCheck]:
    out: list[DqCheck] = []
    for i in items:
        kind = str(i.get("kind", "")).lower()
        field = str(i.get("field", ""))
        sev = DqSeverity(str(i.get("severity", "ERROR")).upper())
        code = str(i.get("code") or kind)
        scope = DqScope(str(i.get("scope", "FIELD")).upper())
        if kind == "not_null":
            out.append(ExpectNotNull(field=field, severity=sev, code=code, scope=scope))
        elif kind == "between":
            out.append(
                ExpectBetween(
                    field=field,
                    min_value=float(i["min_value"]),
                    max_value=float(i["max_value"]),
                    inclusive=bool(i.get("inclusive", True)),
                    severity=sev,
                    code=code,
                    scope=scope,
                )
            )
        elif kind == "in_set":
            vals = i.get("allowed_values")
            if not isinstance(vals, list):
                raise ValueError("allowed_values must be a list")
            out.append(
                ExpectInSet(
                    field=field,
                    allowed_values=tuple(vals),
                    severity=sev,
                    code=code,
                    scope=scope,
                )
            )
        else:
            raise ValueError(f"unknown dq check kind: {kind!r}")
    return out
