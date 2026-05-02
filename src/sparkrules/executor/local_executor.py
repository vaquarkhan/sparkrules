"""LocalRuleExecutor - Python path with compiled closures and alpha network (Requirement 9).

Uses the AlphaNetwork for shared predicate evaluation and Closure_Compiler
output for action computation. Achieves sub-millisecond p99 latency for
50-rule packs on a single fact.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from sparkrules.compiler.alpha_network import AlphaNetwork
from sparkrules.compiler.closure import compile_action
from sparkrules.compiler.rulepack import RulePack
from sparkrules.runtime.engine_metrics import record_score_completed


_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuleFire:
    """Result of a single rule firing."""

    rule_name: str
    salience: int
    fired: bool
    action_output: dict[str, Any]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Result of scoring a single fact against a rule pack."""

    fires: list[RuleFire]
    fired_any: bool
    merged_actions: dict[str, Any]


@dataclass
class LocalRuleExecutor:
    """Python-native rule executor using compiled closures and alpha network (Req 9).

    Usage:
        pack = RulePack.from_drl(drl)
        executor = LocalRuleExecutor.from_rulepack(pack)
        result = executor.score({"t": {"amount": 1500}})
    """

    rulepack: RulePack
    alpha_net: AlphaNetwork
    _action_closures: dict[str, list[tuple[str, Any]]] = field(default_factory=dict)

    @staticmethod
    def from_rulepack(pack: RulePack) -> LocalRuleExecutor:
        """Build a LocalRuleExecutor from a RulePack."""
        asts = [r.ast for r in pack.rules]
        alpha_net = AlphaNetwork.from_rules(asts)

        # Pre-compile action closures for each rule
        action_closures: dict[str, list[tuple[str, Any]]] = {}
        for rule in pack.rules:
            closures = []
            for action in rule.ast.then:
                fname, fn = compile_action(action)
                closures.append((fname, fn))
            action_closures[rule.name] = closures

        return LocalRuleExecutor(
            rulepack=pack,
            alpha_net=alpha_net,
            _action_closures=action_closures,
        )

    @staticmethod
    def from_drl(drl: str) -> LocalRuleExecutor:
        """Build a LocalRuleExecutor directly from DRL text."""
        pack = RulePack.from_drl(drl)
        return LocalRuleExecutor.from_rulepack(pack)

    def score(self, fact: Mapping[str, Any]) -> ScoreResult:
        """Evaluate all rules against a single fact (Req 9, AC 1).

        Returns fired rules ordered by salience with action outputs.
        """
        t0 = time.perf_counter()
        # Shared alpha evaluation
        alpha_fired = self.alpha_net.evaluate(fact)

        fires: list[RuleFire] = []
        merged: dict[str, Any] = {}
        any_fired = False

        # Rules are already salience-ordered in the rulepack
        for rule in self.rulepack.rules:
            fired = alpha_fired.get(rule.name, False)

            action_output: dict[str, Any] = {}
            if fired:
                any_fired = True
                # Compute actions using compiled closures
                for fname, fn in self._action_closures.get(rule.name, []):
                    try:
                        action_output[fname] = fn(fact)
                    except Exception:  # noqa: BLE001  # pragma: no cover
                        action_output[fname] = None

                # Merge actions (highest salience wins — first write wins since sorted)
                for k, v in action_output.items():
                    if k not in merged:
                        merged[k] = v

            fires.append(
                RuleFire(
                    rule_name=rule.name,
                    salience=rule.salience,
                    fired=fired,
                    action_output=action_output,
                    reason_codes=rule.reason_codes,
                )
            )

        elapsed = time.perf_counter() - t0
        fired_rule_names_one_row = [f.rule_name for f in fires if f.fired]
        record_score_completed(
            latency_seconds=elapsed,
            rows=1,
            pack=self.rulepack,
            executor_tag="v2_local",
            fired_rule_names_one_row=fired_rule_names_one_row,
        )
        if _LOG.isEnabledFor(logging.INFO):
            name_to_rule = {r.name: r for r in self.rulepack.rules}
            for fr in fires:
                if fr.fired:
                    cr = name_to_rule[fr.rule_name]
                    _LOG.info(
                        "rule_fired rule=%s strategy=%s salience=%s reason_codes=%s",
                        fr.rule_name,
                        cr.strategy.name,
                        fr.salience,
                        ",".join(fr.reason_codes),
                    )

        return ScoreResult(fires=fires, fired_any=any_fired, merged_actions=merged)

    def apply(self, facts: Sequence[Mapping[str, Any]]) -> list[ScoreResult]:
        """Evaluate all rules against a batch of facts (Req 9, AC 3)."""
        return [self.score(fact) for fact in facts]

    def refresh_rules(self, drl: str) -> None:
        """Hot-swap rules without restarting (Req 23)."""
        new = LocalRuleExecutor.from_drl(drl)
        self.rulepack = new.rulepack
        self.alpha_net = new.alpha_net
        self._action_closures = new._action_closures
