from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from sre.compiler import evaluate_rule
from sre.parser import parse


@dataclass
class SimulationResult:
    rule_name: str
    fired: bool
    action: dict[str, Any]
    bound: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleSimulator:
    _persist: list[Any] = field(default_factory=list, repr=False, init=False)

    def run(
        self, drl: str, fact: MutableMapping[str, Any]
    ) -> SimulationResult:
        r = parse(drl)
        m = evaluate_rule(r, fact)
        return SimulationResult(
            r.name, m.fired, dict(m.action_output), dict(m.bound)
        )
