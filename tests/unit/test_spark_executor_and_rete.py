"""Tests for SparkRuleExecutor (Req 6-8, 10-11, 15-17, 20) and ReteNetwork (Req 25-26)."""

from __future__ import annotations

import json

from sparkrules.compiler.rete import (
    ReteNetwork,
    _extract_field_paths,
    _make_fact_view_class,
    _populate_fact_view,
    _compile_beta_checks,
    _get_field_path,
    _make_comparison_fn,
    _make_reversed_comparison_fn,
)
from sparkrules.spark.dataframe import iter_rule_rows
from sparkrules.spark.executor import (
    SchemaValidationError,
    SparkRuleExecutor,
    _safe_rule_col,
    _safe_action_col,
)
from sparkrules.parser import parse_rules
from sparkrules.parser.ast import (
    BinaryOp,
    BinaryOperator,
    Identifier,
    InExpr,
    ListExpr,
    Literal,
    Not,
)

import pytest


# --- ReteNetwork (Req 25-26) ---


DRL_LENDING = """
rule "credit_low" salience 20 when $f : App( $f.score < 600 ) then result.d = "decline"; end
rule "credit_mid" salience 15 when $f : App( $f.score < 700 ) then result.d = "refer"; end
rule "income_low" salience 10 when $f : App( $f.income < 30000 ) then result.d = "decline"; end
rule "combined" when $f : App( $f.score > 700 and $f.income > 50000 ) then result.d = "approve"; end
"""


def test_rete_evaluate_basic() -> None:
    rules = parse_rules(DRL_LENDING)
    net = ReteNetwork.from_rules(rules)
    result = net.evaluate({"f": {"score": 550, "income": 25000}})
    assert result["credit_low"] is True
    assert result["credit_mid"] is True
    assert result["income_low"] is True
    assert result["combined"] is False


def test_rete_evaluate_no_fire() -> None:
    rules = parse_rules(DRL_LENDING)
    net = ReteNetwork.from_rules(rules)
    result = net.evaluate({"f": {"score": 800, "income": 100000}})
    assert result["credit_low"] is False
    assert result["credit_mid"] is False
    assert result["income_low"] is False
    assert result["combined"] is True


def test_rete_range_merged_alpha() -> None:
    """Req 26: range predicates on same field share extraction."""
    drl = "\n".join(
        f'rule "r{i}" when $f : App( $f.score >= {600 + i * 10} ) then end'
        for i in range(10)
    )
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    # All 10 rules reference f.score - should have 1 alpha extraction
    # (each rule has its own beta check against its threshold)
    assert len(net.path_to_slot) == 1  # only f.score
    result = net.evaluate({"f": {"score": 650}})
    # score >= 600 through 650 should fire (6 rules), 660+ should not
    fired = sum(1 for v in result.values() if v)
    assert fired == 6


def test_rete_wildcard_rules() -> None:
    drl = 'rule "wild" when $t : T ( true ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({})["wild"] is True


def test_rete_multi_fact_wildcard() -> None:
    drl = 'rule "multi" when $a : A ( true ) and $b : B ( true ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({})["multi"] is True


def test_rete_membership_frozenset() -> None:
    """Req 25, AC 5: pre-built frozenset for O(1) in checks."""
    drl = 'rule "r" when $t : T ( $t.status in ["A", "B", "C"] ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert any(isinstance(v, frozenset) for v in net.membership_sets.values())
    assert net.evaluate({"t": {"status": "B"}})["r"] is True
    assert net.evaluate({"t": {"status": "X"}})["r"] is False


def test_rete_not_in() -> None:
    drl = 'rule "r" when $t : T ( $t.x not in [1, 2] ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({"t": {"x": 5}})["r"] is True
    assert net.evaluate({"t": {"x": 1}})["r"] is False


def test_rete_matches() -> None:
    drl = 'rule "r" when $t : T ( $t.name matches "^A.*" ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({"t": {"name": "Alice"}})["r"] is True
    assert net.evaluate({"t": {"name": "Bob"}})["r"] is False


def test_rete_contains() -> None:
    drl = 'rule "r" when $t : T ( $t.tags contains "vip" ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({"t": {"tags": ["vip", "gold"]}})["r"] is True
    assert net.evaluate({"t": {"tags": ["basic"]}})["r"] is False


def test_rete_not_expression() -> None:
    drl = 'rule "r" when $t : T ( not $t.blocked == true ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({"t": {"blocked": False}})["r"] is True


def test_fact_view_class() -> None:
    cls = _make_fact_view_class({"t.x", "t.y"})
    assert hasattr(cls, "__slots__")
    assert "t__x" in cls.__slots__
    assert "t__y" in cls.__slots__


def test_populate_fact_view() -> None:
    cls = _make_fact_view_class({"t.x", "t.y"})
    fv = _populate_fact_view(cls, {"t": {"x": 42, "y": "hello"}}, cls._path_to_slot)
    assert fv.t__x == 42
    assert fv.t__y == "hello"


def test_extract_field_paths() -> None:
    expr = BinaryOp(BinaryOperator.GT, Identifier("$t.amount"), Literal(100))
    paths = _extract_field_paths(expr)
    assert "t.amount" in paths


def test_get_field_path() -> None:
    assert _get_field_path(Identifier("$t.x")) == "t.x"
    assert _get_field_path(Literal(5)) is None


def test_comparison_fns() -> None:
    fn = _make_comparison_fn(BinaryOperator.GT, 5)
    assert fn is not None
    assert fn(10) is True
    assert fn(3) is False
    assert fn(None) is False

    fn2 = _make_reversed_comparison_fn(BinaryOperator.LT, 5)
    assert fn2 is not None
    assert fn2(10) is True  # 5 < 10
    assert fn2(3) is False  # 5 < 3 is False


def test_comparison_all_ops() -> None:
    for op in [BinaryOperator.GT, BinaryOperator.GE, BinaryOperator.LT, BinaryOperator.LE, BinaryOperator.EQ, BinaryOperator.NE]:
        fn = _make_comparison_fn(op, 5)
        assert fn is not None
        fn2 = _make_reversed_comparison_fn(op, 5)
        assert fn2 is not None
    assert _make_comparison_fn(BinaryOperator.AND, 5) is None
    assert _make_reversed_comparison_fn(BinaryOperator.AND, 5) is None


def test_compile_beta_literal_true() -> None:
    checks = _compile_beta_checks(Literal(True), {}, {})
    assert checks == []


def test_compile_beta_literal_false() -> None:
    checks = _compile_beta_checks(Literal(False), {}, {})
    assert checks is None


def test_compile_beta_or_returns_none() -> None:
    expr = BinaryOp(BinaryOperator.OR, Literal(True), Literal(False))
    checks = _compile_beta_checks(expr, {}, {})
    assert checks is None


# --- SparkRuleExecutor helpers ---


def test_safe_rule_col() -> None:
    assert _safe_rule_col("high-value") == "r_high_value"
    assert _safe_rule_col("my rule") == "r_my_rule"


def test_safe_action_col() -> None:
    assert _safe_action_col("discount") == "action_discount"


def test_spark_executor_from_drl() -> None:
    ex = SparkRuleExecutor.from_drl('rule "r" when $t : T ( $t.x > 5 ) then result.ok = true; end')
    assert len(ex.rulepack.rules) == 1


def test_spark_executor_refresh_rules() -> None:
    ex = SparkRuleExecutor.from_drl('rule "old" when $t : T ( true ) then end')
    assert ex.rulepack.rules[0].name == "old"
    ex.refresh_rules('rule "new" when $t : T ( true ) then end')
    assert ex.rulepack.rules[0].name == "new"


def test_schema_validation_error() -> None:
    with pytest.raises(SchemaValidationError):
        raise SchemaValidationError("test error")


# --- iter_rule_rows v2 (Req 19) ---


def test_iter_rule_rows_v2_single_rule() -> None:
    drl = 'rule "r" when $t : T ( $t.x > 5 ) then result.ok = true; end'
    rows = [{"id": "1", "t": {"x": 10}}, {"id": "2", "t": {"x": 3}}]
    results = list(iter_rule_rows(iter(rows), drl, use_v2=True))
    assert len(results) == 2
    assert results[0][1] is True  # fired
    assert results[1][1] is False


def test_iter_rule_rows_v2_multi_rule() -> None:
    drl = """
rule "a" when $t : T ( $t.x > 5 ) then result.a = 1; end
rule "b" when $t : T ( $t.x > 10 ) then result.b = 2; end
"""
    rows = [{"id": "1", "t": {"x": 8}}, {"id": "2", "t": {"x": 15}}]
    results = list(iter_rule_rows(iter(rows), drl, use_v2=True))
    assert results[0][1] is True  # a fires
    assert results[1][1] is True  # both fire
    out2 = json.loads(results[1][2])
    assert out2["action"]["a"] == 1
    assert out2["action"]["b"] == 2


def test_iter_rule_rows_v1_backward_compat() -> None:
    drl = 'rule "r" when $t : T ( $t.x > 5 ) then result.ok = true; end'
    rows = [{"id": "1", "t": {"x": 10}}]
    results = list(iter_rule_rows(iter(rows), drl, use_v2=False))
    assert len(results) == 1
    assert results[0][1] is True


def test_iter_rule_rows_empty_drl() -> None:
    with pytest.raises(ValueError, match="at least one rule"):
        list(iter_rule_rows(iter([]), "", use_v2=True))


def test_iter_rule_rows_dict_row() -> None:
    drl = 'rule "r" when $t : T ( true ) then end'
    rows = [{"id": "x", "t": {}}]
    results = list(iter_rule_rows(iter(rows), drl))
    assert results[0][0] == "x"


def test_rete_complex_predicate_falls_to_wildcard() -> None:
    """Rule with OR predicate can't be beta-compiled, becomes wildcard."""
    drl = 'rule "r" when $t : T ( $t.x > 5 or $t.y < 3 ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert "r" in net.wildcard_rules
    assert net.evaluate({"t": {"x": 1, "y": 10}})["r"] is True  # wildcard always fires


def test_rete_reversed_comparison() -> None:
    """Literal OP $t.field (reversed comparison)."""
    drl = 'rule "r" when $t : T ( 100 < $t.x ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    assert net.evaluate({"t": {"x": 200}})["r"] is True
    assert net.evaluate({"t": {"x": 50}})["r"] is False


def test_rete_empty_rules() -> None:
    net = ReteNetwork.from_rules([])
    assert net.evaluate({}) == {}


def test_iter_rule_rows_v2_action_error() -> None:
    """Action errors degrade to None in v2 path."""
    drl = 'rule "r" when $t : T ( true ) then result.v = $t.missing.deep; end'
    rows = [{"id": "1", "t": {}}]
    results = list(iter_rule_rows(iter(rows), drl, use_v2=True))
    assert results[0][1] is True
    out = json.loads(results[0][2])
    assert out["action"]["v"] is None


def test_rete_and_chain_with_or_child() -> None:
    """AND chain where one child is OR (can't beta-compile) -> wildcard."""
    drl = 'rule "r" when $t : T ( $t.x > 5 and ($t.y > 3 or $t.z < 10) ) then end'
    rules = parse_rules(drl)
    net = ReteNetwork.from_rules(rules)
    # The OR child makes beta compilation fail, so rule becomes wildcard
    assert "r" in net.wildcard_rules
