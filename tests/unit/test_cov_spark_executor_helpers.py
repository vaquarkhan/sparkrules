"""Cover sparkrules.spark.executor helpers without a JVM."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sparkrules.compiler.rulepack import RulePack
from sparkrules.spark import executor as sex


def test_action_staging_merge_plan_sorts_by_salience() -> None:
    drl = (
        "rule lo salience 1 when $t : T ( true ) then result.score = 1; end\n"
        "rule hi salience 9 when $t : T ( true ) then result.score = 9; end"
    )
    pack = RulePack.from_drl(drl)
    cols: set[str] = set()
    for rule in pack.rules:
        for fname in sex._action_fields_from_ast(rule):
            cols.add(sex._staging_action_column(rule, fname))
    plan = sex.action_staging_merge_plan(pack, df_columns=frozenset(cols))
    assert list(plan.keys()) == ["score"]
    ordered = [t[0] for t in plan["score"]]
    assert ordered == [9, 1]


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


def test_common_coalesce_sql_type_branches() -> None:
    pytest.importorskip("pyspark")
    from pyspark.sql.types import (
        ArrayType,
        BooleanType,
        DateType,
        DoubleType,
        IntegerType,
        LongType,
        StringType,
        TimestampType,
    )

    assert sex._common_coalesce_sql_type([]) == "string"
    assert sex._common_coalesce_sql_type([BooleanType(), BooleanType()]) == "boolean"
    assert sex._common_coalesce_sql_type([IntegerType(), LongType()]) == "bigint"
    assert sex._common_coalesce_sql_type([DoubleType(), DoubleType()]) == "double"
    assert sex._common_coalesce_sql_type([StringType()]) == "string"
    assert sex._common_coalesce_sql_type([IntegerType(), StringType()]) == "string"
    assert sex._common_coalesce_sql_type([TimestampType()]) == "timestamp"
    assert sex._common_coalesce_sql_type([DateType()]) == "date"
    assert sex._common_coalesce_sql_type([DateType(), TimestampType()]) == "string"
    assert sex._common_coalesce_sql_type([ArrayType(StringType())]) == "string"


def test_staging_dtypes_for_merge_collects_known_columns() -> None:
    pytest.importorskip("pyspark")
    from pyspark.sql.types import IntegerType, StringType

    f1 = MagicMock()
    f1.name = "action_x__s10_o0"
    f1.dataType = IntegerType()
    f2 = MagicMock()
    f2.name = "other"
    f2.dataType = StringType()
    df = MagicMock()
    df.schema.fields = (f1, f2)
    plan = [(10, "r", 0, "action_x__s10_o0")]
    assert sex._staging_dtypes_for_merge(df, plan) == [IntegerType()]
