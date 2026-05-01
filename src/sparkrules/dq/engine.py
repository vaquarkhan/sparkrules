from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import re
from typing import Any, Iterable, Sequence


class DqSeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class DqScope(str, Enum):
    ROW = "ROW"
    FIELD = "FIELD"
    RELATIONSHIP = "RELATIONSHIP"


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
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectBetween:
    field: str
    min_value: float | int
    max_value: float | int
    inclusive: bool = True
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "between"
    scope: DqScope = DqScope.FIELD
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectInSet:
    field: str
    allowed_values: tuple[Any, ...]
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "in_set"
    scope: DqScope = DqScope.FIELD
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectRegex:
    field: str
    pattern: str
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "regex"
    scope: DqScope = DqScope.FIELD
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectUnique:
    field: str
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "unique"
    scope: DqScope = DqScope.FIELD
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectColumnSumBetween:
    field: str
    min_value: float | int
    max_value: float | int
    inclusive: bool = True
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "sum_between"
    scope: DqScope = DqScope.ROW
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectRowCountWithin:
    min_count: int
    max_count: int
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "row_count_between"
    scope: DqScope = DqScope.ROW
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class ExpectTableCountsToMatch:
    field_a: str
    field_b: str
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "table_counts_match"
    scope: DqScope = DqScope.RELATIONSHIP
    tolerance: float | None = None


@dataclass(frozen=True, slots=True)
class FreshnessCheck:
    field: str
    max_age_seconds: int
    severity: DqSeverity = DqSeverity.ERROR
    code: str = "freshness"
    scope: DqScope = DqScope.FIELD
    tolerance: float | None = None


DqCheck = (
    ExpectNotNull
    | ExpectBetween
    | ExpectInSet
    | ExpectRegex
    | ExpectUnique
    | ExpectColumnSumBetween
    | ExpectRowCountWithin
    | ExpectTableCountsToMatch
    | FreshnessCheck
)


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


def _should_emit(total: int, fail: int, tolerance: float | None) -> bool:
    if fail <= 0:
        return False
    if tolerance is None:
        return True
    if tolerance < 0:
        raise ValueError("tolerance must be >= 0")
    t = max(1, total)
    ratio = float(fail) / float(t)
    return ratio > tolerance


def _parse_ts(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(float(v), tz=UTC)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


class DataQualityEngine:
    def evaluate(
        self,
        fact: dict[str, Any],
        checks: Sequence[DqCheck],
        *,
        rows: Sequence[dict[str, Any]] | None = None,
    ) -> list[DqViolation]:
        out: list[DqViolation] = []
        rs = list(rows) if rows is not None else [fact]
        for c in checks:
            if isinstance(c, ExpectNotNull):
                v = fact.get(c.field)
                fail = 1 if v is None else 0
                if _should_emit(1, fail, c.tolerance):
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
                fail = 0
                if not isinstance(raw, (int, float)):
                    fail = 1
                    msg = f"{c.field!r} is not numeric"
                else:
                    ok = (
                        c.min_value <= raw <= c.max_value
                        if c.inclusive
                        else c.min_value < raw < c.max_value
                    )
                    if ok:
                        fail = 0
                        msg = ""
                    else:
                        fail = 1
                        msg = (
                            f"{c.field!r}={raw} is outside [{c.min_value}, {c.max_value}]"
                            if c.inclusive
                            else f"{c.field!r}={raw} is outside ({c.min_value}, {c.max_value})"
                        )
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=msg,
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectInSet):
                raw = fact.get(c.field)
                fail = 1 if raw not in c.allowed_values else 0
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=f"{c.field!r}={raw!r} is not in {list(c.allowed_values)!r}",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectRegex):
                raw = fact.get(c.field)
                text = "" if raw is None else str(raw)
                fail = 0 if re.search(c.pattern, text) else 1
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=f"{c.field!r}={text!r} does not match /{c.pattern}/",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectUnique):
                vals = [r.get(c.field) for r in rs if r.get(c.field) is not None]
                fail = len(vals) - len(set(vals))
                if _should_emit(len(vals), fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=f"{c.field!r} has {fail} duplicate value(s)",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectColumnSumBetween):
                nums: list[float] = []
                bad = 0
                for r in rs:
                    raw = r.get(c.field)
                    if raw is None:
                        continue
                    if isinstance(raw, (int, float)):
                        nums.append(float(raw))
                    else:
                        bad += 1
                fail = 0
                msg = ""
                if bad > 0:
                    fail = bad
                    msg = f"{c.field!r} has {bad} non-numeric value(s)"
                else:
                    s = sum(nums)
                    ok = (
                        c.min_value <= s <= c.max_value
                        if c.inclusive
                        else c.min_value < s < c.max_value
                    )
                    if not ok:
                        fail = 1
                        msg = (
                            f"sum({c.field!r})={s} is outside [{c.min_value}, {c.max_value}]"
                            if c.inclusive
                            else f"sum({c.field!r})={s} is outside ({c.min_value}, {c.max_value})"
                        )
                if _should_emit(max(1, len(rs)), fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=msg,
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectRowCountWithin):
                n = len(rs)
                ok = c.min_count <= n <= c.max_count
                fail = 0 if ok else 1
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field="*",
                            message=f"row_count={n} is outside [{c.min_count}, {c.max_count}]",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, ExpectTableCountsToMatch):
                a = fact.get(c.field_a)
                b = fact.get(c.field_b)
                ok = (
                    isinstance(a, (int, float))
                    and isinstance(b, (int, float))
                    and float(a) == float(b)
                )
                fail = 0 if ok else 1
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=f"{c.field_a},{c.field_b}",
                            message=f"{c.field_a}={a!r} does not match {c.field_b}={b!r}",
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            if isinstance(c, FreshnessCheck):
                raw = fact.get(c.field)
                dt = _parse_ts(raw)
                fail = 0
                if dt is None:
                    fail = 1
                    msg = f"{c.field!r} is not a valid timestamp"
                else:
                    age = (datetime.now(UTC) - dt).total_seconds()
                    if age <= c.max_age_seconds:
                        fail = 0
                        msg = ""
                    else:
                        fail = 1
                        msg = f"{c.field!r} is stale by {int(age)}s (max {c.max_age_seconds}s)"
                if _should_emit(1, fail, c.tolerance):
                    out.append(
                        DqViolation(
                            code=c.code,
                            field=c.field,
                            message=msg,
                            severity=c.severity,
                            scope=c.scope,
                        )
                    )
                continue
            raise TypeError(type(c).__name__)
        return out


def summarize_violations(items: Sequence[DqViolation]) -> dict[str, int]:
    info_count = sum(1 for x in items if x.severity == DqSeverity.INFO)
    warn_count = sum(1 for x in items if x.severity == DqSeverity.WARN)
    error_count = sum(1 for x in items if x.severity == DqSeverity.ERROR)
    critical_count = sum(1 for x in items if x.severity == DqSeverity.CRITICAL)
    return {
        "info_count": info_count,
        "warn_count": warn_count,
        "error_count": error_count,
        "critical_count": critical_count,
        "total": info_count + warn_count + error_count + critical_count,
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
        tol = i.get("tolerance")
        tolerance = None if tol is None else float(tol)
        if kind == "not_null":
            out.append(
                ExpectNotNull(
                    field=field,
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
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
                    tolerance=tolerance,
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
                    tolerance=tolerance,
                )
            )
        elif kind == "regex":
            pat = i.get("pattern")
            if not isinstance(pat, str) or not pat:
                raise ValueError("pattern must be a non-empty string")
            out.append(
                ExpectRegex(
                    field=field,
                    pattern=pat,
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        elif kind == "unique":
            out.append(
                ExpectUnique(
                    field=field,
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        elif kind == "sum_between":
            out.append(
                ExpectColumnSumBetween(
                    field=field,
                    min_value=float(i["min_value"]),
                    max_value=float(i["max_value"]),
                    inclusive=bool(i.get("inclusive", True)),
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        elif kind == "row_count_between":
            out.append(
                ExpectRowCountWithin(
                    min_count=int(i["min_count"]),
                    max_count=int(i["max_count"]),
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        elif kind == "table_counts_match":
            f2 = i.get("other_field")
            if not isinstance(f2, str) or not f2:
                raise ValueError("other_field is required for table_counts_match")
            out.append(
                ExpectTableCountsToMatch(
                    field_a=field,
                    field_b=f2,
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        elif kind == "freshness":
            out.append(
                FreshnessCheck(
                    field=field,
                    max_age_seconds=int(i["max_age_seconds"]),
                    severity=sev,
                    code=code,
                    scope=scope,
                    tolerance=tolerance,
                )
            )
        else:
            raise ValueError(f"unknown dq check kind: {kind!r}")
    return out
