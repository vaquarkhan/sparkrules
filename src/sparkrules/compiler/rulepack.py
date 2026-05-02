"""RulePack Data Structure (Requirement 5) with Strategy Classification (Requirement 4).

A structured, salience-ordered collection of compiled rules with classification
metadata. Replaces raw DRL strings as the unit of rule distribution.
"""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from sparkrules.compiler.closure import PredicateFn, compile_action, compile_predicate
from sparkrules.compiler.translator import TranslationError, can_translate, translate_action, translate_predicate
from sparkrules.parser import parse_rules
from sparkrules.parser.ast import BinaryOp, BinaryOperator, Expr, FactPattern, RuleAst


class Strategy(Enum):
    SQL_PUSHDOWN = auto()
    ALPHA_SHARED = auto()
    PYTHON_FALLBACK = auto()


@dataclass(frozen=True)
class ClassifiedRule:
    """A rule with its classification metadata."""

    name: str
    salience: int
    strategy: Strategy
    ast: RuleAst
    predicate_sql: str | None  # Only for SQL_PUSHDOWN
    action_sql: dict[str, str]  # field -> SQL expr, only for SQL_PUSHDOWN
    alpha_hashes: tuple[str, ...]  # Structural hashes of atomic predicates
    agenda_group: str
    activation_group: str | None
    stop_on_fire: bool
    reason_codes: tuple[str, ...]


def _hash_expr(expr: Expr) -> str:
    """Structural hash of an expression for alpha-node deduplication."""
    from sparkrules.parser.printer import print_ast_expr

    text = print_ast_expr(expr)
    return hashlib.md5(text.encode()).hexdigest()[:12]


def _flatten_and_chain(expr: Expr) -> list[Expr]:
    """Flatten AND-chained predicates into individual atomic predicates."""
    if isinstance(expr, BinaryOp) and expr.op == BinaryOperator.AND:
        return _flatten_and_chain(expr.left) + _flatten_and_chain(expr.right)
    return [expr]


def classify_rule(rule: RuleAst) -> Strategy:
    """Classify a rule into an execution strategy (Req 4).

    - SQL_PUSHDOWN: single-fact, all predicates translatable to SQL, literal actions
    - ALPHA_SHARED: single-fact, column-only predicates, not fully SQL-translatable
    - PYTHON_FALLBACK: multi-fact, complex expressions, or untranslatable
    """
    # Multi-fact patterns -> fallback
    if len(rule.when) > 1:
        return Strategy.PYTHON_FALLBACK

    # Check if predicates are SQL-translatable
    pattern = rule.when[0]
    if pattern.constraint is None:
        return Strategy.SQL_PUSHDOWN  # pragma: no cover

    if can_translate(pattern.constraint):
        # Check if actions are also translatable
        all_actions_simple = True
        for action in rule.then:
            try:
                translate_action(action)
            except TranslationError:  # pragma: no cover
                all_actions_simple = False
                break
        if all_actions_simple:
            return Strategy.SQL_PUSHDOWN
        return Strategy.ALPHA_SHARED  # pragma: no cover

    return Strategy.ALPHA_SHARED


def _build_classified_rule(rule: RuleAst) -> ClassifiedRule:
    """Build a ClassifiedRule from a RuleAst."""
    strategy = classify_rule(rule)

    predicate_sql: str | None = None
    action_sql: dict[str, str] = {}

    if strategy == Strategy.SQL_PUSHDOWN:
        pattern = rule.when[0]
        if pattern.constraint is not None:
            try:
                predicate_sql = translate_predicate(pattern.constraint)
            except TranslationError:  # pragma: no cover
                strategy = Strategy.ALPHA_SHARED
        for action in rule.then:
            try:
                fname, sql = translate_action(action)
                action_sql[fname] = sql
            except TranslationError:  # pragma: no cover
                strategy = Strategy.ALPHA_SHARED
                action_sql = {}
                break

    # Compute alpha hashes
    alpha_hashes: list[str] = []
    for pattern in rule.when:
        if pattern.constraint is not None:
            for atomic in _flatten_and_chain(pattern.constraint):
                alpha_hashes.append(_hash_expr(atomic))

    return ClassifiedRule(
        name=rule.name,
        salience=rule.salience,
        strategy=strategy,
        ast=rule,
        predicate_sql=predicate_sql,
        action_sql=action_sql,
        alpha_hashes=tuple(alpha_hashes),
        agenda_group=rule.agenda_group,
        activation_group=rule.activation_group,
        stop_on_fire=rule.stop_on_fire,
        reason_codes=rule.reason_codes,
    )


@dataclass
class RulePack:
    """Structured, salience-ordered collection of classified rules (Req 5)."""

    rules: list[ClassifiedRule]
    sql_pushdown: list[ClassifiedRule]
    alpha_shared: list[ClassifiedRule]
    python_fallback: list[ClassifiedRule]
    drl_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_drl(drl: str, **metadata: Any) -> RulePack:
        """Build a RulePack from DRL text."""
        asts = parse_rules(drl)
        classified = [_build_classified_rule(r) for r in asts]
        classified.sort(key=lambda r: -r.salience)

        sql_rules = [r for r in classified if r.strategy == Strategy.SQL_PUSHDOWN]
        alpha_rules = [r for r in classified if r.strategy == Strategy.ALPHA_SHARED]
        fallback_rules = [r for r in classified if r.strategy == Strategy.PYTHON_FALLBACK]

        drl_hash = hashlib.sha256(drl.encode()).hexdigest()

        return RulePack(
            rules=classified,
            sql_pushdown=sql_rules,
            alpha_shared=alpha_rules,
            python_fallback=fallback_rules,
            drl_hash=drl_hash,
            metadata=dict(metadata),
        )

    def serialize(self) -> bytes:
        """Serialize for Spark broadcast (Req 20)."""
        return pickle.dumps(self, protocol=4)

    @staticmethod
    def deserialize(data: bytes) -> RulePack:
        obj = pickle.loads(data)  # noqa: S301
        if not isinstance(obj, RulePack):
            raise TypeError("invalid RulePack")
        return obj

    def summary(self) -> dict[str, Any]:
        return {
            "total_rules": len(self.rules),
            "sql_pushdown": len(self.sql_pushdown),
            "alpha_shared": len(self.alpha_shared),
            "python_fallback": len(self.python_fallback),
            "drl_hash": self.drl_hash[:16],
        }
