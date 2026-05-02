"""RulePack Data Structure (Requirement 5) with Strategy Classification (Requirement 4).

A structured, salience-ordered collection of compiled rules with classification
metadata. Replaces raw DRL strings as the unit of rule distribution.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from sparkrules.compiler.translator import (
    TranslationError,
    can_translate,
    translate_action,
    translate_predicate,
)
from sparkrules.compiler.exceptions import RulePackVersionError
from sparkrules.parser import parse_rules
from sparkrules.parser.ast import BinaryOp, BinaryOperator, Expr, InExpr, Literal, Not, RuleAst


_LOG = logging.getLogger(__name__)

# Serialized artifact envelope (major, minor): bump minor for additive pickles; bump major for breaks.
_RULEPACK_MAGIC = b"SRRP"
RULEPACK_SER_MAJOR_VERSION = 1
RULEPACK_SER_MINOR_VERSION = 0
RULEPACK_LARGE_SERIALIZE_WARN_BYTES = 4 * 1024 * 1024


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
    source_order: int = 0
    classification_rationale: str = ""


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


def _has_python_only_regex(expr: Expr) -> bool:
    """Check if expression contains regex patterns with Python-only features (Req 21).

    Python regex features NOT supported by Spark RLIKE:
    - Lookahead: (?=...), (?!...)
    - Lookbehind: (?<=...), (?<!...)
    - Atomic groups: (?>...)
    - Possessive quantifiers: *+, ++, ?+
    - Named groups: (?P<name>...)
    """
    import re as _re

    PYTHON_ONLY = _re.compile(r"\(\?[=!<P>]|\*\+|\+\+|\?\+")

    if isinstance(expr, BinaryOp):
        if expr.op == BinaryOperator.MATCHES and isinstance(expr.right, Literal):
            pattern = str(expr.right.value)
            if PYTHON_ONLY.search(pattern):
                return True
        return _has_python_only_regex(expr.left) or _has_python_only_regex(expr.right)
    if isinstance(expr, Not):
        return _has_python_only_regex(expr.expr)
    if isinstance(expr, InExpr):
        return _has_python_only_regex(expr.left) or _has_python_only_regex(expr.right)
    return False


def classify_rule_with_rationale(rule: RuleAst) -> tuple[Strategy, str]:
    """Return strategy plus a stable diagnostic code for logs / Req 31."""

    if len(rule.when) > 1:
        return Strategy.PYTHON_FALLBACK, "MULTI_FACT_PATTERN"

    pattern = rule.when[0]
    if pattern.constraint is None:
        return Strategy.SQL_PUSHDOWN, "NO_WHEN_CONSTRAINT"  # pragma: no cover

    if not can_translate(pattern.constraint):
        return Strategy.ALPHA_SHARED, "PREDICATE_NOT_SQL_TRANSLATABLE"

    if _has_python_only_regex(pattern.constraint):
        return Strategy.PYTHON_FALLBACK, "PYTHON_ONLY_REGEX"

    for action in rule.then:
        try:
            translate_action(action)
        except TranslationError:  # pragma: no cover
            return Strategy.ALPHA_SHARED, "ACTION_NOT_SQL_TRANSLATABLE"

    return Strategy.SQL_PUSHDOWN, "SQL_PUSH_TRANSLATABLE"


def classify_rule(rule: RuleAst) -> Strategy:
    """Classify a rule into an execution strategy (Req 4).

    - SQL_PUSHDOWN: single-fact, all predicates translatable to SQL, literal actions
    - ALPHA_SHARED: single-fact, column-only predicates, not fully SQL-translatable
    - PYTHON_FALLBACK: multi-fact, complex expressions, or untranslatable
    """

    return classify_rule_with_rationale(rule)[0]


def _build_classified_rule(rule: RuleAst, *, source_order: int) -> ClassifiedRule:
    """Build a ClassifiedRule from a RuleAst."""

    strategy, rationale = classify_rule_with_rationale(rule)

    predicate_sql: str | None = None
    action_sql: dict[str, str] = {}

    if strategy == Strategy.SQL_PUSHDOWN:
        pattern = rule.when[0]
        if pattern.constraint is not None:
            try:
                predicate_sql = translate_predicate(pattern.constraint)
            except TranslationError:  # pragma: no cover
                from sparkrules.runtime.engine_metrics import record_translation_failure

                record_translation_failure()
                strategy = Strategy.ALPHA_SHARED
                rationale = "PREDICATE_TRANSLATION_RUNTIME_FAIL"
        if strategy == Strategy.SQL_PUSHDOWN:
            for action in rule.then:
                try:
                    fname, sql = translate_action(action)
                    action_sql[fname] = sql
                except TranslationError:  # pragma: no cover
                    from sparkrules.runtime.engine_metrics import record_translation_failure

                    record_translation_failure()
                    strategy = Strategy.ALPHA_SHARED
                    rationale = "ACTION_TRANSLATION_RUNTIME_FAIL"
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
        source_order=source_order,
        classification_rationale=rationale,
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
        classified = [_build_classified_rule(r, source_order=i) for i, r in enumerate(asts)]
        # Req 17: deterministic ordering — (-salience, rule name NFC ascending, declaration order ascending)
        classified.sort(key=lambda r: (-r.salience, r.name, r.source_order))

        sql_rules = [r for r in classified if r.strategy == Strategy.SQL_PUSHDOWN]
        alpha_rules = [r for r in classified if r.strategy == Strategy.ALPHA_SHARED]
        fallback_rules = [r for r in classified if r.strategy == Strategy.PYTHON_FALLBACK]

        drl_hash = hashlib.sha256(drl.encode()).hexdigest()

        pack = RulePack(
            rules=classified,
            sql_pushdown=sql_rules,
            alpha_shared=alpha_rules,
            python_fallback=fallback_rules,
            drl_hash=drl_hash,
            metadata=dict(metadata),
        )
        from sparkrules.runtime.engine_metrics import record_rulepack_classified

        record_rulepack_classified(pack)
        return pack

    def summary(self) -> dict[str, Any]:
        return {
            "total_rules": len(self.rules),
            "sql_pushdown": len(self.sql_pushdown),
            "alpha_shared": len(self.alpha_shared),
            "python_fallback": len(self.python_fallback),
            "drl_hash": self.drl_hash[:16],
            "serialization_major": RULEPACK_SER_MAJOR_VERSION,
            "serialization_minor": RULEPACK_SER_MINOR_VERSION,
        }

    def debug_classification(self) -> list[dict[str, Any]]:
        """Machine-readable classifier breakdown (Req 31)."""
        return [
            {
                "rule": r.name,
                "strategy": r.strategy.name,
                "salience": r.salience,
                "source_order": r.source_order,
                "agenda_group": r.agenda_group,
                "activation_group": r.activation_group,
                "predicate_sql": r.predicate_sql,
                "alpha_hashes": r.alpha_hashes,
                "classification_rationale": r.classification_rationale,
            }
            for r in self.rules
        ]

    def _serialization_envelope_header(self) -> bytes:
        return (
            _RULEPACK_MAGIC
            + bytes([RULEPACK_SER_MAJOR_VERSION])
            + bytes([RULEPACK_SER_MINOR_VERSION])
        )

    def serialize(self) -> bytes:
        """Serialize for Spark broadcast with explicit format version header (Req 20, Req 34)."""
        envelope = self._serialization_envelope_header()
        payload = pickle.dumps(self, protocol=4)
        out = envelope + payload
        from sparkrules.runtime.engine_metrics import max_rulepack_bytes_from_environ

        cap = max_rulepack_bytes_from_environ()
        if cap is not None and len(out) > cap:
            raise ValueError(
                f"RulePack serialized size {len(out)} exceeds SPARKRULES_MAX_RULEPACK_BYTES={cap} (Req 32)"
            )
        if len(out) > RULEPACK_LARGE_SERIALIZE_WARN_BYTES:
            _LOG.warning(
                "RulePack.serialize produced %s bytes (soft guideline %s, Req 32)",
                len(out),
                RULEPACK_LARGE_SERIALIZE_WARN_BYTES,
            )
        return out

    @staticmethod
    def deserialize(data: bytes) -> RulePack:
        offset = 0
        payload = data
        if (
            len(data) >= len(_RULEPACK_MAGIC) + 2
            and data[: len(_RULEPACK_MAGIC)] == _RULEPACK_MAGIC
        ):
            maj = data[len(_RULEPACK_MAGIC)]
            minor = data[len(_RULEPACK_MAGIC) + 1]
            offset = len(_RULEPACK_MAGIC) + 2
            if maj != RULEPACK_SER_MAJOR_VERSION or minor != RULEPACK_SER_MINOR_VERSION:
                raise RulePackVersionError(f"unsupported RulePack format {maj}.{minor}")
            payload = data[offset:]
        obj = pickle.loads(payload)  # noqa: S301
        if not isinstance(obj, RulePack):
            raise TypeError("invalid RulePack")
        return obj
