"""Two-pattern (binary) join eligibility: both ``when`` constraints must hold (Rete beta slice)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sparkrules.compiler.evaluator import evaluate_expr
from sparkrules.parser.ast import RuleAst


def dual_pattern_rule_names(rules: Sequence[RuleAst]) -> frozenset[str]:
    return frozenset(r.name for r in rules if len(r.when) == 2)


def eligible_dual_join_names(rules: Sequence[RuleAst], facts: Mapping[str, Any]) -> frozenset[str]:
    """Rules with exactly two patterns whose predicate conjunction passes on ``facts``."""
    env = dict(facts)
    ok: set[str] = set()
    for r in rules:
        if len(r.when) != 2:
            continue
        p0, p1 = r.when
        try:
            a = True if p0.constraint is None else bool(evaluate_expr(p0.constraint, env))
            b = True if p1.constraint is None else bool(evaluate_expr(p1.constraint, env))
            if a and b:
                ok.add(r.name)
        except Exception:  # noqa: BLE001
            pass
    return frozenset(ok)


def refine_eligibility_with_beta_join(
    alpha_eligible: frozenset[str],
    rules: Sequence[RuleAst],
    facts: Mapping[str, Any],
) -> frozenset[str]:
    """Shrink alpha-only eligibility for dual-pattern rules to those passing a binary join."""
    dual = dual_pattern_rule_names(rules)
    beta_ok = eligible_dual_join_names(rules, facts)
    return frozenset(n for n in alpha_eligible if n not in dual or n in beta_ok)
