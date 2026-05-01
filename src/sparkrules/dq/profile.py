"""Statistical profiling for data quality — "enough DQ to not need Great Expectations."

Computes per-field statistics over a batch of rows: completeness, uniqueness,
mean/stddev/min/max/quantiles for numeric fields, and top-N value counts for
categorical fields.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class NumericStats:
    count: int
    null_count: int
    mean: float
    stddev: float
    min_val: float
    max_val: float
    p25: float
    p50: float
    p75: float


@dataclass(frozen=True, slots=True)
class FieldProfile:
    field_name: str
    total_rows: int
    null_count: int
    completeness: float
    distinct_count: int
    uniqueness: float
    is_numeric: bool
    numeric_stats: NumericStats | None = None
    top_values: tuple[tuple[str, int], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "field": self.field_name,
            "total_rows": self.total_rows,
            "null_count": self.null_count,
            "completeness": round(self.completeness, 4),
            "distinct_count": self.distinct_count,
            "uniqueness": round(self.uniqueness, 4),
            "is_numeric": self.is_numeric,
        }
        if self.numeric_stats:
            ns = self.numeric_stats
            d["stats"] = {
                "count": ns.count,
                "mean": round(ns.mean, 4),
                "stddev": round(ns.stddev, 4),
                "min": ns.min_val,
                "max": ns.max_val,
                "p25": ns.p25,
                "p50": ns.p50,
                "p75": ns.p75,
            }
        if self.top_values:
            d["top_values"] = [{"value": v, "count": c} for v, c in self.top_values]
        return d


@dataclass(frozen=True, slots=True)
class DataProfile:
    total_rows: int
    total_fields: int
    fields: tuple[FieldProfile, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "total_fields": self.total_fields,
            "fields": [f.to_dict() for f in self.fields],
        }


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def profile_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    top_n: int = 5,
    fields: Sequence[str] | None = None,
) -> DataProfile:
    """Compute statistical profile over a batch of rows.

    Args:
        rows: Sequence of fact dicts.
        top_n: Number of top values to include for categorical fields.
        fields: Specific fields to profile. If None, profiles all fields found.

    Returns:
        DataProfile with per-field statistics.
    """
    if not rows:
        return DataProfile(total_rows=0, total_fields=0, fields=())

    all_fields: list[str]
    if fields is not None:
        all_fields = list(fields)
    else:
        seen: dict[str, None] = {}
        for r in rows:
            for k in r:
                if k not in seen:
                    seen[k] = None
        all_fields = list(seen)

    total = len(rows)
    profiles: list[FieldProfile] = []

    for fname in all_fields:
        values: list[Any] = [r.get(fname) for r in rows]
        null_count = sum(1 for v in values if v is None)
        non_null = [v for v in values if v is not None]
        completeness = (total - null_count) / total if total > 0 else 0.0

        distinct = set()
        value_counts: dict[str, int] = {}
        numeric_vals: list[float] = []
        is_numeric = True

        for v in non_null:
            sv = str(v)
            distinct.add(sv)
            value_counts[sv] = value_counts.get(sv, 0) + 1
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric_vals.append(float(v))
            else:
                is_numeric = False

        distinct_count = len(distinct)
        uniqueness = distinct_count / len(non_null) if non_null else 0.0

        ns: NumericStats | None = None
        if is_numeric and numeric_vals:
            n = len(numeric_vals)
            mean = sum(numeric_vals) / n
            variance = sum((x - mean) ** 2 for x in numeric_vals) / n if n > 1 else 0.0
            stddev = math.sqrt(variance)
            sorted_v = sorted(numeric_vals)
            ns = NumericStats(
                count=n,
                null_count=null_count,
                mean=mean,
                stddev=stddev,
                min_val=sorted_v[0],
                max_val=sorted_v[-1],
                p25=_percentile(sorted_v, 0.25),
                p50=_percentile(sorted_v, 0.50),
                p75=_percentile(sorted_v, 0.75),
            )

        top = sorted(value_counts.items(), key=lambda kv: -kv[1])[:top_n]

        profiles.append(
            FieldProfile(
                field_name=fname,
                total_rows=total,
                null_count=null_count,
                completeness=completeness,
                distinct_count=distinct_count,
                uniqueness=uniqueness,
                is_numeric=is_numeric and bool(numeric_vals),
                numeric_stats=ns,
                top_values=tuple(top),
            )
        )

    return DataProfile(
        total_rows=total,
        total_fields=len(profiles),
        fields=tuple(profiles),
    )
