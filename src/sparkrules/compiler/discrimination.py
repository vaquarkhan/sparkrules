from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from sparkrules.compiler.evaluator import evaluate_rule
from sparkrules.parser import parse
from sparkrules.parser.ast import Expr, RuleAst


@dataclass
class AlphaNode:
    name: str
    expr: Expr | None
    child_rules: set[str] = field(default_factory=set)
    eval_counter: int = 0


@dataclass
class DiscriminationNetwork:
    by_rule: dict[str, RuleAst] = field(default_factory=dict)
    eval_counter: int = 0

    @staticmethod
    def build(rules: Mapping[str, str]) -> DiscriminationNetwork:
        dn = DiscriminationNetwork()
        for rid, source in rules.items():
            dn.by_rule[rid] = parse(source)
        return dn

    def evaluate(self, rule_id: str, facts: MutableMapping[str, Any]) -> bool:
        r = self.by_rule[rule_id]
        m = evaluate_rule(r, facts)
        self.eval_counter += 1
        return m.fired
