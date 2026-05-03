"""Tests for Pandas batch evaluation (Requirement 22)."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")

from sparkrules.compiler.rulepack import RulePack
from sparkrules.executor.pandas_executor import apply_pandas, _spark_sql_to_pandas


DRL = """
rule "high" salience 10 when $t : T ( $t.amount > 1000 ) then result.risk = "high"; end
rule "low" salience 5 when $t : T ( $t.amount <= 500 ) then result.risk = "low"; end
"""


def test_apply_pandas_basic() -> None:
    pack = RulePack.from_drl(DRL)
    df = pd.DataFrame(
        [
            {"t": {"amount": 1500}},
            {"t": {"amount": 300}},
            {"t": {"amount": 800}},
        ]
    )
    result = apply_pandas(pack, df)
    assert "r_high" in result.columns
    assert "r_low" in result.columns
    assert "fired_any" in result.columns
    assert result["r_high"].iloc[0] is True or result["r_high"].iloc[0] == True  # noqa: E712
    assert result["r_low"].iloc[1] is True or result["r_low"].iloc[1] == True  # noqa: E712


def test_apply_pandas_action_columns() -> None:
    pack = RulePack.from_drl(DRL)
    df = pd.DataFrame([{"t": {"amount": 1500}}, {"t": {"amount": 300}}])
    result = apply_pandas(pack, df)
    assert "action_risk" in result.columns


def test_apply_pandas_fired_any() -> None:
    pack = RulePack.from_drl(DRL)
    df = pd.DataFrame([{"t": {"amount": 800}}])  # neither rule fires
    result = apply_pandas(pack, df)
    assert result["fired_any"].iloc[0] == False  # noqa: E712


def test_apply_pandas_empty_df() -> None:
    pack = RulePack.from_drl('rule "r" when $t : T ( $t.x > 5 ) then end')
    df = pd.DataFrame(columns=["t"])
    result = apply_pandas(pack, df)
    assert "r_r" in result.columns
    assert "fired_any" in result.columns


def test_spark_sql_to_pandas_conversion() -> None:
    assert "==" in _spark_sql_to_pandas("(t.x = 5)")
    assert "&" in _spark_sql_to_pandas("(a AND b)")
    assert "|" in _spark_sql_to_pandas("(a OR b)")
    assert "~" in _spark_sql_to_pandas("NOT a")


def test_spark_sql_to_pandas_preserves_and_inside_literals() -> None:
    out = _spark_sql_to_pandas("(t.ok = true AND t.msg = 'paid AND settled')")
    assert "'paid AND settled'" in out
    assert "&" in out.replace("'paid AND settled'", "")


def test_transform_spark_sql_handles_doubled_quotes_inside_literal() -> None:
    """Inside ``''`` SQL escapes must not treat `` AND `` as pandas ``&``."""
    out = _spark_sql_to_pandas("(flag = true AND txt = 'it''s high AND urgent')")
    assert "high AND urgent" in out


def test_spark_sql_to_pandas_rlike_raises() -> None:
    with pytest.raises(ValueError, match="RLIKE"):
        _spark_sql_to_pandas("(name RLIKE '^A.*')")


def test_apply_pandas_regex_rule_falls_to_closure() -> None:
    """Regex rules can't use pandas.eval, should fall back to closure."""
    drl = 'rule "r" when $t : T ( $t.name matches "^A.*" ) then result.ok = true; end'
    pack = RulePack.from_drl(drl)
    df = pd.DataFrame([{"t": {"name": "Alice"}}, {"t": {"name": "Bob"}}])
    result = apply_pandas(pack, df)
    assert result["r_r"].iloc[0] == True  # noqa: E712
    assert result["r_r"].iloc[1] == False  # noqa: E712


def test_apply_pandas_eval_fallback_to_closure() -> None:
    """Cover pandas.eval fallback when SQL can't be converted."""
    drl = 'rule "r" when $t : T ( $t.tags contains "vip" ) then result.ok = true; end'
    pack = RulePack.from_drl(drl)
    df = pd.DataFrame([{"t": {"tags": ["vip"]}}, {"t": {"tags": ["basic"]}}])
    result = apply_pandas(pack, df)
    assert result["r_r"].iloc[0] == True  # noqa: E712


def test_apply_pandas_no_rules() -> None:
    """Cover fired_any=False when no rules exist."""
    # Create a pack with no rules by using empty DRL trick
    from sparkrules.compiler.rulepack import RulePack as RP

    pack = RP(rules=[], sql_pushdown=[], alpha_shared=[], python_fallback=[], drl_hash="x")
    df = pd.DataFrame([{"x": 1}])
    result = apply_pandas(pack, df)
    assert result["fired_any"].iloc[0] == False  # noqa: E712


def test_apply_pandas_alpha_shared_rule() -> None:
    """Cover the non-SQL_PUSHDOWN closure path (lines 72-73)."""
    # Multi-fact rule -> PYTHON_FALLBACK, uses closure path
    drl = 'rule "r" when $a : A ( true ) and $b : B ( true ) then result.ok = true; end'
    pack = RulePack.from_drl(drl)
    assert pack.rules[0].strategy.name == "PYTHON_FALLBACK"
    df = pd.DataFrame([{"a": {}, "b": {}}])
    result = apply_pandas(pack, df)
    assert "r_r" in result.columns
