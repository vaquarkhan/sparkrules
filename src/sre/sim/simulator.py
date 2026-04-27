from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from sre.compiler import evaluate_rule
from sre.parser import parse, parse_rules
from sre.runtime.rule_chain import ChainExecutionPolicy, RuleChainResult, run_rule_chain


@dataclass
class SimulationResult:
    rule_name: str
    fired: bool
    action: dict[str, Any]
    bound: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainSimulationResult:
    chain: RuleChainResult
    any_fired: bool


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

    def run_chain(
        self,
        drl: str,
        fact: MutableMapping[str, Any],
        *,
        stop_on_decline: bool = False,
        agenda_group_modes: dict[str, str] | None = None,
    ) -> ChainSimulationResult:
        rules = parse_rules(drl)
        cr = run_rule_chain(
            rules,
            dict(fact),
            ChainExecutionPolicy(
                stop_on_decline=stop_on_decline,
                agenda_group_modes=dict(agenda_group_modes or {}),
            ),
        )
        return ChainSimulationResult(
            cr,
            any_fired=bool(cr.last_fired),
        )
