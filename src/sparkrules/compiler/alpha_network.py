"""Alpha Network with closure-compiled evaluation (Requirement 3).

Flattens AND-chains from rule predicates, deduplicates by structural hash,
and shares evaluation of identical sub-predicates across rules. Uses
Closure_Compiler output instead of AST-walking evaluate_expr.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from sparkrules.compiler.closure import PredicateFn, compile_predicate
from sparkrules.parser.ast import BinaryOp, BinaryOperator, Expr, RuleAst
from sparkrules.parser.printer import print_ast_expr


def _flatten_and(expr: Expr) -> list[Expr]:
    """Flatten AND-chained predicates into atomic predicates."""
    if isinstance(expr, BinaryOp) and expr.op == BinaryOperator.AND:
        return _flatten_and(expr.left) + _flatten_and(expr.right)
    return [expr]


def _structural_hash(expr: Expr) -> str:
    """Structural hash for alpha-node deduplication."""
    text = print_ast_expr(expr)
    return hashlib.md5(text.encode()).hexdigest()[:16]


@dataclass
class AlphaNodeV2:
    """A single shared predicate node with a compiled closure."""

    hash_key: str
    expr: Expr
    closure: PredicateFn
    rule_names: set[str] = field(default_factory=set)
    eval_count: int = 0


@dataclass
class RuleAlphaMapping:
    """Maps a rule to its required alpha node hashes."""

    rule_name: str
    alpha_hashes: tuple[str, ...]
    is_wildcard: bool  # True if rule has no constraint (always fires)


@dataclass
class AlphaNetwork:
    """Closure-compiled alpha network with shared predicate evaluation (Req 3).

    Evaluates each unique predicate at most once per fact, regardless of
    how many rules reference it. Returns a per-rule fired/not-fired map.
    """

    nodes: dict[str, AlphaNodeV2] = field(default_factory=dict)
    rule_mappings: list[RuleAlphaMapping] = field(default_factory=list)
    total_predicates: int = 0
    unique_alphas: int = 0

    @staticmethod
    def from_rules(rules: Sequence[RuleAst]) -> AlphaNetwork:
        """Build an AlphaNetwork from a list of RuleAst objects."""
        net = AlphaNetwork()
        total_preds = 0

        for rule in rules:
            if len(rule.when) != 1 or rule.when[0].constraint is None:
                # Wildcard or multi-fact: always eligible
                net.rule_mappings.append(
                    RuleAlphaMapping(rule.name, alpha_hashes=(), is_wildcard=True)
                )
                continue

            constraint = rule.when[0].constraint
            atomics = _flatten_and(constraint)
            total_preds += len(atomics)
            hashes: list[str] = []

            for atomic in atomics:
                h = _structural_hash(atomic)
                hashes.append(h)
                if h not in net.nodes:
                    closure = compile_predicate(atomic)
                    net.nodes[h] = AlphaNodeV2(hash_key=h, expr=atomic, closure=closure)
                net.nodes[h].rule_names.add(rule.name)

            net.rule_mappings.append(
                RuleAlphaMapping(rule.name, alpha_hashes=tuple(hashes), is_wildcard=False)
            )

        net.total_predicates = total_preds
        net.unique_alphas = len(net.nodes)
        return net

    @property
    def sharing_ratio(self) -> float:
        """Total predicates / unique alphas. Higher = more sharing."""
        if self.unique_alphas == 0:
            return 0.0
        return self.total_predicates / self.unique_alphas

    def evaluate(self, fact: Mapping[str, Any]) -> dict[str, bool]:
        """Evaluate all rules against a fact, sharing alpha-node evaluation.

        Each unique alpha node is evaluated at most once per call.

        Returns:
            Dict mapping rule_name -> fired (bool).
        """
        # Phase 1: evaluate each unique alpha node once
        alpha_results: dict[str, bool] = {}
        for h, node in self.nodes.items():
            node.eval_count += 1
            alpha_results[h] = node.closure(fact)

        # Phase 2: compute per-rule fired status
        rule_results: dict[str, bool] = {}
        for mapping in self.rule_mappings:
            if mapping.is_wildcard:
                rule_results[mapping.rule_name] = True
                continue
            # Rule fires if ALL its alpha nodes are True
            fired = all(alpha_results.get(h, False) for h in mapping.alpha_hashes)
            rule_results[mapping.rule_name] = fired

        return rule_results
