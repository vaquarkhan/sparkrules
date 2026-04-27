from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence


class DqSeverity(str, Enum):
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class DqViolation:
    code: str
    field: str
    message: str
    severity: DqSeverity


@dataclass(frozen=True, slots=True)
class ExpectNotNull:
    field: str
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "not_null"


@dataclass(frozen=True, slots=True)
class ExpectBetween:
    field: str
    min_value: float | int
    max_value: float | int
    inclusive: bool = True
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "between"


@dataclass(frozen=True, slots=True)
class ExpectInSet:
    field: str
    allowed_values: tuple[Any, ...]
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "in_set"


DqCheck = ExpectNotNull | ExpectBetween | ExpectInSet


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
                        )
                    )
                continue
            raise TypeError(type(c).__name__)
        return out


def checks_from_api(items: Iterable[dict[str, Any]]) -> list[DqCheck]:
    out: list[DqCheck] = []
    for i in items:
        kind = str(i.get("kind", "")).lower()
        field = str(i.get("field", ""))
        sev = DqSeverity(str(i.get("severity", "ERROR")).upper())
        code = str(i.get("code") or kind)
        if kind == "not_null":
            out.append(ExpectNotNull(field=field, severity=sev, code=code))
        elif kind == "between":
            out.append(
                ExpectBetween(
                    field=field,
                    min_value=float(i["min_value"]),
                    max_value=float(i["max_value"]),
                    inclusive=bool(i.get("inclusive", True)),
                    severity=sev,
                    code=code,
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
                )
            )
        else:
            raise ValueError(f"unknown dq check kind: {kind!r}")
    return out
