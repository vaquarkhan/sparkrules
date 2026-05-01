from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping

from sparkrules.compiler import evaluate_rule
from sparkrules.parser import parse


def _extract_path(r: Mapping[str, Any], path: str) -> Any:
    cur: Any = r
    for part in path.split("."):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(part)
    return cur


def _row_group_key(r: Mapping[str, Any], group_by: tuple[str, ...]) -> tuple[Any, ...]:
    if not group_by:
        return ()
    return tuple(_extract_path(r, k) for k in group_by)


@dataclass
class QuotaAggregate:
    key: tuple[Any, ...]
    value: float


@dataclass
class TwoPassResult:
    pass1_fired: list[str] = field(default_factory=list)
    pass2_fired: list[str] = field(default_factory=list)
    aggregates: list[QuotaAggregate] = field(
        default_factory=list
    )


@dataclass
class TwoPassOrchestrator:
    """Two-pass evaluation: Pass1 qualifies rows; Pass2 runs only on qualifiers.

    When ``group_by`` is non-empty, ``aggregates`` holds Pass1 fire counts per group key.
    When ``quota_per_group`` is set, Pass2 runs at most that many times per group key
    (in row order among Pass1-qualified rows).
    """

    pass1_drl: str
    pass2_drl: str
    group_by: tuple[str, ...] = field(default_factory=tuple)
    quota_per_group: int | None = None

    def run(self, rows: list[Mapping[str, Any]]) -> TwoPassResult:  # noqa: C901, E501
        r1 = parse(self.pass1_drl)
        r2 = parse(self.pass2_drl)
        result = TwoPassResult()
        p1_qualified: list[tuple[tuple[Any, ...], Mapping[str, Any]]] = []
        counts: dict[tuple[Any, ...], int] = defaultdict(int)

        for r in rows:
            env: dict[str, Any] = {k: v for k, v in r.items()}
            m1 = evaluate_rule(r1, env)
            if m1.fired:
                result.pass1_fired.append(str(r1.name))
                key = _row_group_key(r, self.group_by)
                counts[key] += 1
                p1_qualified.append((key, r))

        result.aggregates = [
            QuotaAggregate(key=k, value=float(v))
            for k, v in sorted(counts.items(), key=lambda kv: str(kv[0]))
        ]

        consumed: dict[tuple[Any, ...], int] = defaultdict(int)
        for key, r in p1_qualified:
            if self.quota_per_group is not None:
                if consumed[key] >= self.quota_per_group:
                    continue
                consumed[key] += 1
            m2 = evaluate_rule(r2, {k: v for k, v in r.items()})
            if m2.fired:
                result.pass2_fired.append(str(r2.name))
        return result
