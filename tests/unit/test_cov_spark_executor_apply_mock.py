"""Cover ``SparkRuleExecutor.apply`` without a working JVM (strategies monkeypatched)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pyspark")
from pyspark.sql.types import (  # noqa: E402
    BooleanType,
    StringType,
    StructField,
    StructType,
)

from sparkrules.compiler.rulepack import RulePack  # noqa: E402
from sparkrules.spark.executor import SchemaValidationError, SparkRuleExecutor  # noqa: E402


def test_spark_rule_executor_apply_rejects_maptype_facts_column() -> None:
    from pyspark.sql.types import MapType

    drl = 'rule "ok" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    bad = StructType([StructField("bad", MapType(StringType(), StringType()), True)])
    df = MagicMock()
    df.schema = bad
    with pytest.raises(SchemaValidationError, match="MapType"):
        ex.apply(df)


def test_spark_rule_executor_apply_rejects_invalid_output_format() -> None:
    drl = 'rule "ok" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])
    with pytest.raises(ValueError, match="output_format"):
        ex.apply(df, output_format="json")


def test_spark_rule_executor_merge_actions_single_staging_no_coalesce() -> None:
    """Single contributing rule uses cast-only merge path (no ``coalesce``)."""

    drl = 'rule "only" when $t : T ( true ) then result.score = 1; end'
    ex = SparkRuleExecutor.from_drl(drl)

    f_id = MagicMock()
    f_id.name = "id"
    f_id.dataType = StringType()
    f_st = MagicMock()
    f_st.name = "action_score__s0_o0"
    f_st.dataType = StringType()

    class _Chain:
        def __init__(self) -> None:
            self._cols = ["id", "action_score__s0_o0"]
            self.schema = MagicMock()
            self.schema.fields = [f_id, f_st]

        @property
        def columns(self) -> list[str]:
            return self._cols

        def withColumn(self, _name: str, _expr: object) -> _Chain:
            self._cols = self._cols + [_name]
            return self

        def drop(self, *names: str) -> _Chain:
            for n in names:
                if n in self._cols:
                    self._cols.remove(n)
            return self

    chain = _Chain()
    mexpr = MagicMock()
    with patch("pyspark.sql.functions.col", return_value=mexpr):
        out = ex._merge_actions(chain)
    assert "action_score" in out.columns
    assert "action_score__s0_o0" not in out.columns


def test_spark_rule_executor_to_narrow_output_select() -> None:
    """Cover narrow projection: ``fired_rules``, ``actions``, ``fired_any``."""

    drl = 'rule "ok" when $t : T ( true ) then result.flag = true; end'
    ex = SparkRuleExecutor.from_drl(drl)
    result = MagicMock()
    result.columns = ["id", "r_ok", "action_flag", "fired_any"]
    narrow_out = MagicMock()
    result.select = MagicMock(return_value=narrow_out)

    wm = MagicMock()
    wm.otherwise.return_value = MagicMock()

    def _when(*_a: object, **_k: object) -> MagicMock:
        return wm

    with patch("pyspark.sql.functions.when", side_effect=_when):
        with patch("pyspark.sql.functions.array_compact", return_value=MagicMock()):
            with patch("pyspark.sql.functions.array", return_value=MagicMock()):
                with patch("pyspark.sql.functions.struct", return_value=MagicMock()):
                    with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                        with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                            out = ex._to_narrow_output(result)
    assert out is narrow_out
    result.select.assert_called_once()


def test_spark_rule_executor_to_narrow_empty_fired_and_struct_from_merge_plan() -> None:
    """No ``r_*`` columns -> empty ``fired_rules`` array; plan + merged action -> ``actions`` struct."""

    drl = 'rule "x" when $t : T ( true ) then result.score = 1; end'
    ex = SparkRuleExecutor.from_drl(drl)
    result = MagicMock()
    result.columns = ["id", "action_score__s0_o0", "action_score", "fired_any"]
    narrow_out = MagicMock()
    result.select = MagicMock(return_value=narrow_out)
    arr_root = MagicMock()
    arr_root.cast = MagicMock(return_value=MagicMock())

    with patch("pyspark.sql.functions.array", return_value=arr_root):
        with patch("pyspark.sql.functions.struct", return_value=MagicMock()):
            with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                    out = ex._to_narrow_output(result)
    assert out is narrow_out
    arr_root.cast.assert_called_once_with("array<string>")


def test_spark_rule_executor_apply_with_counts_single_agg() -> None:
    drl = 'rule "ok" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])

    class _Row:
        def __getitem__(self, key: str) -> int:
            return {"r_ok": 11, "_total_rows": 500}[key]

    agg_df = MagicMock()
    agg_df.collect.return_value = [_Row()]
    wide = MagicMock()
    wide.columns = ["id", "r_ok", "fired_any"]
    wide.agg = MagicMock(return_value=agg_df)

    sum_mock = MagicMock()
    count_col = MagicMock()
    count_col.alias = MagicMock(return_value=MagicMock())
    with patch.object(ex, "apply", return_value=wide):
        with patch("pyspark.sql.functions.sum", return_value=sum_mock):
            with patch("pyspark.sql.functions.count", return_value=count_col):
                with patch("pyspark.sql.functions.when", return_value=MagicMock()):
                    with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                        with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                            out_df, counts = ex.apply_with_counts(df)
    assert out_df is wide
    assert counts == {"r_ok": 11, "_total_rows": 500}
    wide.agg.assert_called_once()


def test_spark_rule_executor_apply_fired_any_with_mocked_strategies() -> None:
    """Monkeypatch A/B/C/merge and stub ``F.greatest`` so ``apply`` completes without Spark SQL."""

    drl = 'rule "a" when $t : T ( true ) then end\nrule "b" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])

    merged = MagicMock()
    merged.columns = ["id", "r_a", "r_b"]
    merged.schema = StructType(
        [
            StructField("id", StringType(), True),
            StructField("r_a", BooleanType(), True),
            StructField("r_b", BooleanType(), True),
        ],
    )
    mfinal = MagicMock()
    mfinal.columns = ["id", "r_a", "r_b", "fired_any"]
    merged.withColumn = MagicMock(return_value=mfinal)

    ex._apply_strategy_a = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_b = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_c = lambda d: merged  # type: ignore[method-assign]
    ex._merge_actions = lambda d: merged  # type: ignore[method-assign]

    mcol = MagicMock()
    with patch("pyspark.sql.functions.greatest", return_value=mcol):
        with patch("pyspark.sql.functions.col", return_value=mcol):
            with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                out = ex.apply(df)
    assert out is mfinal
    merged.withColumn.assert_called_once()


def test_spark_rule_executor_apply_fired_any_single_rule_uses_col_only() -> None:
    """Single-rule packs must not call ``greatest`` (Spark requires ≥2 args)."""

    drl = 'rule "ok" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])

    merged = MagicMock()
    merged.columns = ["id", "r_ok"]
    mfinal = MagicMock()
    merged.withColumn = MagicMock(return_value=mfinal)

    ex._apply_strategy_a = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_b = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_c = lambda d: merged  # type: ignore[method-assign]
    ex._merge_actions = lambda d: merged  # type: ignore[method-assign]

    mcol = MagicMock()
    with patch("pyspark.sql.functions.greatest") as m_greatest:
        with patch("pyspark.sql.functions.col", return_value=mcol):
            with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                out = ex.apply(df)
    assert out is mfinal
    m_greatest.assert_not_called()
    merged.withColumn.assert_called_once_with("fired_any", mcol)


def test_spark_rule_executor_apply_fired_any_false_when_no_rule_cols_on_df() -> None:
    """If rule boolean columns were dropped upstream, ``fired_any`` must still be consistent."""

    drl = 'rule "ok" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])

    merged = MagicMock()
    merged.columns = ["id"]
    mfinal = MagicMock()
    merged.withColumn = MagicMock(return_value=mfinal)

    ex._apply_strategy_a = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_b = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_c = lambda d: merged  # type: ignore[method-assign]
    ex._merge_actions = lambda d: merged  # type: ignore[method-assign]

    lit_false = MagicMock()
    with patch("pyspark.sql.functions.greatest") as m_greatest:
        with patch("pyspark.sql.functions.lit", return_value=lit_false):
            out = ex.apply(df)
    assert out is mfinal
    m_greatest.assert_not_called()
    merged.withColumn.assert_called_once_with("fired_any", lit_false)


def test_spark_rule_executor_apply_narrow_delegates_to_to_narrow_output() -> None:
    drl = 'rule "a" when $t : T ( true ) then end\nrule "b" when $t : T ( true ) then end'
    ex = SparkRuleExecutor.from_drl(drl)
    df = MagicMock()
    df.schema = StructType([StructField("id", StringType(), True)])
    merged = MagicMock()
    merged.columns = ["id", "r_a", "r_b"]
    mfinal = MagicMock()
    mfinal.columns = ["id", "r_a", "r_b", "fired_any"]
    merged.withColumn = MagicMock(return_value=mfinal)
    ex._apply_strategy_a = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_b = lambda d: merged  # type: ignore[method-assign]
    ex._apply_strategy_c = lambda d: merged  # type: ignore[method-assign]
    ex._merge_actions = lambda d: merged  # type: ignore[method-assign]
    narrow_df = MagicMock()
    mcol = MagicMock()
    with patch("pyspark.sql.functions.greatest", return_value=mcol):
        with patch("pyspark.sql.functions.col", return_value=mcol):
            with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                with patch.object(ex, "_to_narrow_output", return_value=narrow_df) as m_narrow:
                    out = ex.apply(df, output_format="narrow")
    assert out is narrow_df
    m_narrow.assert_called_once_with(mfinal)


def test_spark_rule_executor_merge_actions_coalesce_and_drop() -> None:
    """Cover ``_merge_actions`` cast + ``coalesce`` + staging column drops."""

    drl = (
        "rule hi salience 2 when $t : T ( true ) then result.score = 9; end\n"
        "rule lo salience 1 when $t : T ( true ) then result.score = 1; end\n"
    )
    ex = SparkRuleExecutor.from_drl(drl)

    from pyspark.sql.types import IntegerType

    f_id = MagicMock()
    f_id.name = "id"
    f_id.dataType = StringType()
    f_hi = MagicMock()
    f_hi.name = "action_score__s2_o0"
    f_hi.dataType = IntegerType()
    f_lo = MagicMock()
    f_lo.name = "action_score__s1_o1"
    f_lo.dataType = IntegerType()

    class _Chain:
        def __init__(self) -> None:
            self._cols = ["id", "action_score__s2_o0", "action_score__s1_o1"]
            self.schema = MagicMock()
            self.schema.fields = [f_id, f_hi, f_lo]

        @property
        def columns(self) -> list[str]:
            return self._cols

        def withColumn(self, name: str, expr: object) -> _Chain:
            self._cols = self._cols + [name]
            return self

        def drop(self, *names: str) -> _Chain:
            for n in names:
                if n in self._cols:
                    self._cols.remove(n)
            return self

    chain = _Chain()
    mexpr = MagicMock()
    with patch("pyspark.sql.functions.col", return_value=mexpr):
        with patch("pyspark.sql.functions.coalesce", return_value=mexpr):
            out = ex._merge_actions(chain)
    assert "action_score" in out.columns
    assert "action_score__s2_o0" not in out.columns
    assert "action_score__s1_o1" not in out.columns


def test_spark_rule_executor_apply_strategy_a_no_predicate_sql_uses_lit_true() -> None:
    import dataclasses

    drl = 'rule "r" when $t : T ( true ) then result.flag = true; end'
    ex = SparkRuleExecutor.from_drl(drl)
    cr0 = ex.rulepack.sql_pushdown[0]
    ex.rulepack.sql_pushdown[0] = dataclasses.replace(cr0, predicate_sql=None)

    class _Chain:
        columns = ["t"]

        def select(self, *_a: object, **_k: object) -> _Chain:
            return self

    df = _Chain()
    lit_m = MagicMock()
    expr_m = MagicMock()

    def _make_when(*_a: object, **_k: object) -> MagicMock:
        w = MagicMock()
        w.otherwise.return_value = MagicMock()
        return w

    with patch("pyspark.sql.functions.when", side_effect=_make_when):
        with patch("pyspark.sql.functions.expr", return_value=expr_m):
            with patch("pyspark.sql.functions.lit", return_value=lit_m):
                with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                    out = ex._apply_strategy_a(df)
    assert out is df


def test_spark_rule_executor_apply_strategy_a_sql_pushdown_with_column() -> None:
    """Exercise Strategy A predicate + action ``withColumn`` wiring (mocked Spark expr fns)."""

    drl = 'rule "r" when $t : T ( $t.n > 0 ) then result.flag = true; end'
    ex = SparkRuleExecutor.from_drl(drl)
    assert ex.rulepack.sql_pushdown, "expected SQL_PUSHDOWN classification"

    class _Chain:
        columns = ["t"]

        def select(self, *_a: object, **_k: object) -> _Chain:
            return self

    df = _Chain()
    lit_m = MagicMock()
    expr_m = MagicMock()

    def _make_when(*_a: object, **_k: object) -> MagicMock:
        w = MagicMock()
        w.otherwise.return_value = MagicMock()
        return w

    with patch("pyspark.sql.functions.when", side_effect=_make_when):
        with patch("pyspark.sql.functions.expr", return_value=expr_m):
            with patch("pyspark.sql.functions.lit", return_value=lit_m):
                with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                    out = ex._apply_strategy_a(df)
    assert out is df


def test_spark_rule_executor_apply_strategy_c_partition_paths_and_action_error() -> None:
    """Drive Strategy C closure: broadcast, partition eval, row shapes, action exception."""

    drl = "rule p when $t : T ( 1 in $t.opts ) then result.q = 1; end"
    ex = SparkRuleExecutor.from_drl(drl)
    assert ex.rulepack.python_fallback, "expected PYTHON_FALLBACK for dynamic IN"

    df = MagicMock()
    spark = MagicMock()
    df.sparkSession = spark
    sc = MagicMock()
    spark.sparkContext = sc
    sc.broadcast.side_effect = lambda v: MagicMock(value=v)  # type: ignore[method-assign]

    captured: list[object] = []

    def _capture_map_partitions(fn: object) -> MagicMock:
        captured.append(fn)
        return MagicMock()

    df.rdd.mapPartitions = _capture_map_partitions  # type: ignore[method-assign]

    out_df = MagicMock()
    spark.createDataFrame.return_value = out_df

    ex._apply_strategy_c(df)
    assert captured and callable(captured[0])
    part_fn = captured[0]

    from pyspark.sql import Row

    class _RowTypeErr:
        def asDict(self, recursive: bool = False) -> dict:
            if recursive:
                raise TypeError("no recursive")
            return {"t": {"opts": [1]}}

    class _SeqRow:
        def __iter__(self) -> object:
            return iter([("t", {"opts": [1]})])

    from sparkrules.compiler import closure as closure_mod

    real_ca = closure_mod.compile_action

    def _exploding_compile(action: object) -> tuple[str, object]:
        fname, _fn = real_ca(action)

        def _boom(_fact: object) -> None:
            raise RuntimeError("action failure for coverage")

        return fname, _boom

    with patch.object(closure_mod, "compile_action", _exploding_compile):
        list(part_fn([_RowTypeErr()]))
    list(part_fn([_SeqRow()]))

    spark.createDataFrame.assert_called_once()


def test_spark_rule_executor_apply_strategy_b_with_patched_alpha_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dataclasses

    from sparkrules.compiler import rulepack as rp
    from sparkrules.model.rule import DEFAULT_AGENDA_GROUP
    from sparkrules.parser import parse
    from sparkrules.parser.ast import FactPattern, RuleAst

    class _Opaque:
        pass

    real = parse("rule a when $t : T ( $t.x > 1 ) then result.s = 1; end")
    fake_rule = RuleAst(
        name="alpha_only",
        salience=0,
        agenda_group=DEFAULT_AGENDA_GROUP,
        activation_group=None,
        pass_name=None,
        group_by=(),
        reason_codes=(),
        stop_on_fire=False,
        when=(FactPattern("t", "T", _Opaque()),),  # type: ignore[arg-type]
        then=real.then,
    )
    alpha_cr = rp._build_classified_rule(fake_rule, source_order=0)
    node_expr = real.when[0].constraint
    h0, h1 = "ha0", "hb1"
    alpha_cr2 = dataclasses.replace(alpha_cr, alpha_hashes=(h0, h1))
    net = MagicMock()
    node = MagicMock()
    node.expr = node_expr
    net.nodes = {h0: node, h1: node}

    sql_pack = RulePack.from_drl("rule s when $t : T ( true ) then end")
    sql_cr = sql_pack.rules[0]
    pack = RulePack(
        rules=[sql_cr, alpha_cr2],
        sql_pushdown=[sql_cr],
        alpha_shared=[alpha_cr2],
        python_fallback=[],
        drl_hash="mixb",
    )
    ex = SparkRuleExecutor(rulepack=pack, _drl="")

    class _Chain:
        columns: list[str] = []

        def select(self, *_a: object, **_k: object) -> _Chain:
            return self

        def drop(self, *_a: object, **_k: object) -> _Chain:
            return self

    import pyspark.sql.functions as psf

    def _fake_when(*_a: object, **_k: object) -> MagicMock:
        w = MagicMock()
        w.otherwise.return_value = MagicMock()
        return w

    monkeypatch.setattr(psf, "when", _fake_when)

    expr_m = MagicMock()
    expr_m.cast.return_value = MagicMock()
    col_m = MagicMock()
    col_m.__and__ = MagicMock(return_value=col_m)
    col_m.alias = MagicMock(return_value=col_m)

    tp_calls = {"n": 0}

    def _tp_side(*_a: object, **_k: object) -> str:
        tp_calls["n"] += 1
        if tp_calls["n"] == 1:
            raise ValueError("simulated alpha translate failure")
        return "true"

    with patch("sparkrules.spark.executor.AlphaNetwork.from_rules", return_value=net):
        with patch("sparkrules.spark.executor.translate_predicate", side_effect=_tp_side):
            with patch("pyspark.sql.functions.expr", return_value=expr_m):
                with patch("pyspark.sql.functions.col", return_value=col_m):
                    with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                        out = ex._apply_strategy_b(_Chain())
    assert out is not None
    assert tp_calls["n"] == 2


def test_spark_rule_executor_apply_strategy_b_no_alpha_nodes_uses_lit_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dataclasses

    from sparkrules.compiler import rulepack as rp
    from sparkrules.model.rule import DEFAULT_AGENDA_GROUP
    from sparkrules.parser import parse
    from sparkrules.parser.ast import FactPattern, RuleAst

    class _Opaque:
        pass

    real = parse("rule a when $t : T ( $t.x > 1 ) then result.s = 1; end")
    fake_rule = RuleAst(
        name="alpha_empty",
        salience=0,
        agenda_group=DEFAULT_AGENDA_GROUP,
        activation_group=None,
        pass_name=None,
        group_by=(),
        reason_codes=(),
        stop_on_fire=False,
        when=(FactPattern("t", "T", _Opaque()),),  # type: ignore[arg-type]
        then=real.then,
    )
    alpha_cr = rp._build_classified_rule(fake_rule, source_order=0)
    alpha_cr2 = dataclasses.replace(alpha_cr, alpha_hashes=())
    pack = RulePack(
        rules=[alpha_cr2],
        sql_pushdown=[],
        alpha_shared=[alpha_cr2],
        python_fallback=[],
        drl_hash="emptya",
    )
    ex = SparkRuleExecutor(rulepack=pack, _drl="")

    class _Chain:
        columns: list[str] = []

        def select(self, *_a: object, **_k: object) -> _Chain:
            return self

        def drop(self, *_a: object, **_k: object) -> _Chain:
            return self

    import pyspark.sql.functions as psf

    def _fake_when(*_a: object, **_k: object) -> MagicMock:
        w = MagicMock()
        w.otherwise.return_value = MagicMock()
        return w

    monkeypatch.setattr(psf, "when", _fake_when)

    net = MagicMock()
    net.nodes = {}

    expr_m = MagicMock()
    expr_m.cast.return_value = MagicMock()

    with patch("sparkrules.spark.executor.AlphaNetwork.from_rules", return_value=net):
        with patch("pyspark.sql.functions.expr", return_value=expr_m):
            with patch("pyspark.sql.functions.col", return_value=MagicMock()):
                with patch("pyspark.sql.functions.lit", return_value=MagicMock()):
                    out = ex._apply_strategy_b(_Chain())
    assert out is not None


def test_spark_rule_executor_strategy_buckets_noop_on_empty_pack() -> None:
    empty = RulePack(
        rules=[],
        sql_pushdown=[],
        alpha_shared=[],
        python_fallback=[],
        drl_hash="0",
    )
    ex = SparkRuleExecutor(rulepack=empty, _drl="")
    sentinel = object()
    assert ex._apply_strategy_a(sentinel) is sentinel
    assert ex._apply_strategy_b(sentinel) is sentinel
    assert ex._apply_strategy_c(sentinel) is sentinel


def test_spark_rule_executor_apply_fired_any_literal_false_when_no_rules() -> None:
    empty = RulePack(
        rules=[],
        sql_pushdown=[],
        alpha_shared=[],
        python_fallback=[],
        drl_hash="0",
    )
    ex = SparkRuleExecutor(rulepack=empty, _drl="")
    df = MagicMock()
    df.schema = StructType([])

    class _Base:
        def __init__(self) -> None:
            self.columns: list[str] = []
            self.schema = StructType([])
            self.with_column_calls: list[tuple[str, object]] = []

        def withColumn(self, name: str, expr: object) -> _Base:
            self.with_column_calls.append((name, expr))
            self.columns.append(name)
            return self

    base = _Base()

    ex._apply_strategy_a = lambda d: base  # type: ignore[method-assign]
    ex._apply_strategy_b = lambda d: base  # type: ignore[method-assign]
    ex._apply_strategy_c = lambda d: base  # type: ignore[method-assign]
    ex._merge_actions = lambda d: base  # type: ignore[method-assign]

    lit_false = MagicMock()
    with patch("pyspark.sql.functions.lit", return_value=lit_false):
        out = ex.apply(df)
    assert out is base
    assert base.with_column_calls[-1][0] == "fired_any"
    assert base.with_column_calls[-1][1] is lit_false
