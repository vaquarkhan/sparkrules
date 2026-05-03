"""Cover sparkrules.spark.executor helpers without a JVM."""

from __future__ import annotations

import pytest

from sparkrules.compiler.rulepack import RulePack
from sparkrules.spark import executor as sex


def test_assert_safe_generated_column_passes() -> None:
    sex._assert_machine_generated_alias("r_simple_rule")


def test_assert_safe_generated_column_rejects() -> None:
    with pytest.raises(sex.SchemaValidationError):
        sex._assert_machine_generated_alias("r_has-hyphen_bad")


def test_staging_action_helpers() -> None:
    drl = 'rule "rule_a" when $t : T ( true ) then result.flag = true; end'
    pack = RulePack.from_drl(drl)
    rule = pack.rules[0]
    assert sex._staging_action_flat(
        rule.salience, rule.source_order, "flag"
    ) == sex._staging_action_column(rule, "flag")


def test_action_fields_from_ast_multiple_outputs() -> None:
    drl = "rule mr when $t : T ( true ) then result.u = 1; result.v = 2; end"
    pack = RulePack.from_drl(drl)
    rule = pack.rules[0]
    assert sex._action_fields_from_ast(rule) == ["u", "v"]


def test_safe_rule_col_sanitizes() -> None:
    assert sex._safe_rule_col('My "Quoted" Rule') == "r_My_Quoted_Rule"


def test_spark_rule_executor_construct_and_refresh() -> None:
    drl1 = "rule rx when $t : T ( true ) then end"
    drl2 = "rule ry when $t : T ( true ) then end"
    ex = sex.SparkRuleExecutor.from_drl(drl1)
    assert ex._drl == drl1 and len(ex.rulepack.rules) == 1
    ex.refresh_rules(drl2)
    assert ex._drl == drl2 and ex.rulepack.rules[0].name == "ry"
