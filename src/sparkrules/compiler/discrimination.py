from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Sequence

import sparkrules.parser.ast as A
from sparkrules.compiler.evaluator import evaluate_expr, evaluate_rule
from sparkrules.parser import parse
from sparkrules.parser.ast import Expr, RuleAst


def _freeze_expr(e: Expr) -> object:
    """Hashable structural key for sharing alpha nodes (Rete-style predicate indexing)."""
    if isinstance(e, A.Literal):
        return ("lit", e.value)
    if isinstance(e, A.Identifier):
        return ("id", e.name)
    if isinstance(e, A.Not):
        return ("not", _freeze_expr(e.expr))
    if isinstance(e, A.ListExpr):
        return ("list", tuple(_freeze_expr(x) for x in e.items))
    if isinstance(e, A.InExpr):
        return ("in", _freeze_expr(e.left), _freeze_expr(e.right), e.negated)
    if isinstance(e, A.FieldAccess):
        return ("field", e.base, e.field)
    if isinstance(e, A.CallExpr):
        return ("call", e.name, tuple(_freeze_expr(a) for a in e.args))
    if isinstance(e, A.BinaryOp):
        return ("bin", e.op.name, _freeze_expr(e.left), _freeze_expr(e.right))
    raise TypeError(type(e).__name__)  # pragma: no cover — parser-only Expr types


@dataclass
class AlphaNode:
    """Shared first-pattern constraint bucket (single eval per bucket per fact snapshot)."""

    name: str
    expr: Expr | None
    child_ast_names: set[str] = field(default_factory=set)
    eval_counter: int = 0


@dataclass
class DiscriminationNetwork:
    """Cheap alpha-net over first ``when`` pattern; keyed by compilation id for ``evaluate``."""

    # External rule id -> AST (compilation / store key — must match StrategyClassifier inputs).
    by_rule: dict[str, RuleAst] = field(default_factory=dict)
    eval_counter: int = 0
    alpha_eval_counter: int = 0
    _wildcard_ast_names: set[str] = field(default_factory=set)
    _alpha_nodes: dict[tuple[str, str, object], AlphaNode] = field(default_factory=dict)

    @staticmethod
    def build(rules: Mapping[str, str]) -> DiscriminationNetwork:
        by_ast = {rid: parse(src) for rid, src in rules.items()}
        return DiscriminationNetwork._from_external_map(by_ast)

    @staticmethod
    def from_asts(rule_asts: Sequence[RuleAst]) -> DiscriminationNetwork:
        by_ast = {r.name: r for r in rule_asts}
        return DiscriminationNetwork._from_external_map(by_ast)

    @staticmethod
    def _from_external_map(by_external: Mapping[str, RuleAst]) -> DiscriminationNetwork:
        dn = DiscriminationNetwork(by_rule=dict(by_external))
        for ast in by_external.values():
            if len(ast.when) != 1:
                dn._wildcard_ast_names.add(ast.name)
                continue
            pat = ast.when[0]
            if pat.constraint is None:
                dn._wildcard_ast_names.add(ast.name)
                continue
            key = (pat.fact_type, pat.bind_name, _freeze_expr(pat.constraint))
            node = dn._alpha_nodes.get(key)
            if node is None:
                node = AlphaNode(name=f"α:{pat.fact_type}:{pat.bind_name}", expr=pat.constraint)
                dn._alpha_nodes[key] = node
            node.child_ast_names.add(ast.name)
        return dn

    def eligible_rule_names(self, facts: Mapping[str, Any]) -> frozenset[str]:
        """Rule AST names whose first-pattern alpha test may pass (shared eval per alpha node).

        Matches :func:`run_rule_chain` comparisons on ``RuleAst.name``.
        """
        env = dict(facts)
        names: set[str] = set(self._wildcard_ast_names)
        for node in self._alpha_nodes.values():
            node.eval_counter += 1
            self.alpha_eval_counter += 1
            try:
                if evaluate_expr(node.expr, env):
                    names |= node.child_ast_names
            except Exception:  # noqa: BLE001
                pass
        return frozenset(names)

    def evaluate(self, rule_id: str, facts: MutableMapping[str, Any]) -> bool:
        r = self.by_rule[rule_id]
        m = evaluate_rule(r, facts)
        self.eval_counter += 1
        return m.fired
