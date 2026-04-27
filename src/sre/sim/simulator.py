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
class ShadowSimulationResult:
    primary: SimulationResult
    shadow: SimulationResult
    drifted: bool
    drift_fields: tuple[str, ...]


@dataclass
class RuleCoverageItem:
    rule_name: str
    fired_count: int
    total: int
    fire_rate: float


@dataclass
class CoverageSimulationResult:
    total_facts: int
    total_rules: int
    covered_rules: int
    items: list[RuleCoverageItem]


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

    def run_shadow(
        self,
        primary_drl: str,
        shadow_drl: str,
        fact: MutableMapping[str, Any],
    ) -> ShadowSimulationResult:
        p = self.run(primary_drl, dict(fact))
        s = self.run(shadow_drl, dict(fact))
        fields: set[str] = set(p.action) | set(s.action)
        drift = tuple(sorted(k for k in fields if p.action.get(k) != s.action.get(k)))
        return ShadowSimulationResult(
            primary=p,
            shadow=s,
            drifted=bool(drift),
            drift_fields=drift,
        )

    def analyze_coverage(
        self,
        drl: str,
        facts: list[Mapping[str, Any]],
    ) -> CoverageSimulationResult:
        rules = parse_rules(drl)
        totals = len(facts)
        items: list[RuleCoverageItem] = []
        for r in rules:
            fired = 0
            for f in facts:
                m = evaluate_rule(r, dict(f))
                if m.fired:
                    fired += 1
            rate = (fired / totals) if totals > 0 else 0.0
            items.append(
                RuleCoverageItem(
                    rule_name=r.name,
                    fired_count=fired,
                    total=totals,
                    fire_rate=rate,
                )
            )
        covered = sum(1 for it in items if it.fired_count > 0)
        return CoverageSimulationResult(
            total_facts=totals,
            total_rules=len(items),
            covered_rules=covered,
            items=items,
        )
