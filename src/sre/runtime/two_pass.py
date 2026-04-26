from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from sre.compiler import evaluate_rule
from sre.parser import parse


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
    pass1_drl: str
    pass2_drl: str
    group_by: tuple[str, ...] = field(default_factory=tuple)

    def run(self, rows: list[Mapping[str, Any]]) -> TwoPassResult:  # noqa: C901, E501
        r1 = parse(self.pass1_drl)
        r2 = parse(self.pass2_drl)
        result = TwoPassResult()
        p1_qualified: list[Mapping[str, Any]] = []
        for r in rows:
            env: dict[str, Any] = {k: v for k, v in r.items()}
            m1 = evaluate_rule(r1, env)
            if m1.fired:
                result.pass1_fired.append(str(r1.name))
                p1_qualified.append(r)
        for r in p1_qualified:
            m2 = evaluate_rule(r2, {k: v for k, v in r.items()})
            if m2.fired:
                result.pass2_fired.append(str(r2.name))
        return result
