from __future__ import annotations

import pytest

from sparkrules.model import (
    CollectAggregateError,
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    OverlappingRowsError,
    Row,
    dt_from_json,
    dt_to_json,
    evaluate_decision_table,
)


def _dt(
    hp: HitPolicy,
    rows: tuple[Row, ...],
    op: str = "==",
) -> DecisionTable:
    return DecisionTable(
        "t",
        hp,
        (InputColumn("i", "f", ColumnType.INT, op),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        rows,
    )


def test_ops_ne_gt() -> None:
    t = _dt(
        HitPolicy.FIRST,
        (Row((1, "a"), 0), Row((2, "b"), 0)),
        op="!=",
    )
    # != rejects row when v == cell; f=0 matches first row, f=1 only second
    assert evaluate_decision_table(t, {"f": 0})["o"] == "a"
    assert evaluate_decision_table(t, {"f": 1})["o"] == "b"
    u = _dt(HitPolicy.FIRST, (Row((2, "a"), 0),), op=">")
    assert evaluate_decision_table(u, {"f": 3})["o"] == "a"


def test_ops_compare_edge_and_wildcard() -> None:
    t = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (
            InputColumn("i", "f", ColumnType.INT, "<="),
            InputColumn("j", "g", ColumnType.INT, ">="),
        ),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((1, 2, "x"), 0),),
    )
    assert evaluate_decision_table(t, {"f": 1, "g": 2})["o"] == "x"
    s = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.STRING, "=="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row(("*", "y"), 0),),
    )
    assert evaluate_decision_table(s, {"f": "any"})["o"] == "y"


def test_short_row_no_match() -> None:
    t = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("a", "f", ColumnType.INT, "=="), InputColumn("b", "g", ColumnType.INT, "==")),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((1,), 0),),
    )
    assert evaluate_decision_table(t, {"f": 1, "g": 2}) is None


def test_unique_one_row() -> None:
    t = _dt(HitPolicy.UNIQUE, (Row((1, "a"), 0),), op="==")
    assert evaluate_decision_table(t, {"f": 1})["o"] == "a"


def test_collect_all_matching_rows() -> None:
    t = _dt(
        HitPolicy.COLLECT,
        (Row((1, "a"), 0), Row((1, "b"), 0)),
    )
    out = evaluate_decision_table(t, {"f": 1})
    assert out == [{"o": "a"}, {"o": "b"}]


def test_json_enum_string_col() -> None:
    t = DecisionTable(
        "z",
        HitPolicy.PRIORITY,
        (InputColumn("i", "f", ColumnType.STRING, "=="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row(("a", "b"), 5),),
    )
    s = dt_to_json(t)
    t2 = dt_from_json(s)
    assert t2.input_columns[0].col_type == ColumnType.STRING
    u = _dt(
        HitPolicy.PRIORITY,
        (Row((1, "p"), 2), Row((1, "q"), 3)),
    )
    assert evaluate_decision_table(u, {"f": 1})["o"] == "q"


def test_unique_overlaps() -> None:
    t = _dt(
        HitPolicy.UNIQUE,
        (Row((1, "a"), 0), Row((1, "b"), 0)),
    )
    with pytest.raises(OverlappingRowsError):
        evaluate_decision_table(t, {"f": 1})


def test_cmp_lt_none_and_nonnumeric() -> None:
    t = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, "<"),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((5, "a"), 0),),
    )
    assert evaluate_decision_table(t, {"f": None}) is None
    assert evaluate_decision_table(t, {"f": "x"}) is None
    t2 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, "<="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((3, "z"), 0),),
    )
    assert evaluate_decision_table(t2, {"f": 2})["o"] == "z"
    t3 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, ">"),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((1, "g"), 0),),
    )
    assert evaluate_decision_table(t3, {"f": 2})["o"] == "g"
    t4 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, ">="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((2, "h"), 0),),
    )
    assert evaluate_decision_table(t4, {"f": 2})["o"] == "h"


def test_eq_mismatch() -> None:
    t = _dt(HitPolicy.FIRST, (Row((2, "n"), 0),))
    assert evaluate_decision_table(t, {"f": 1}) is None


def test_cmp_fails_on_numeric_compare() -> None:
    t = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, "<"),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((2, "a"), 0),),
    )
    assert evaluate_decision_table(t, {"f": 3}) is None
    t2 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, "<="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((2, "a"), 0),),
    )
    assert evaluate_decision_table(t2, {"f": 3}) is None
    t3 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, ">"),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((3, "a"), 0),),
    )
    assert evaluate_decision_table(t3, {"f": 1}) is None
    t4 = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.INT, ">="),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row((3, "a"), 0),),
    )
    assert evaluate_decision_table(t4, {"f": 1}) is None


def test_custom_operator_acts_like_eq() -> None:
    t = DecisionTable(
        "t",
        HitPolicy.FIRST,
        (InputColumn("i", "f", ColumnType.STRING, "custom"),),
        (OutputColumn("o", "o", ColumnType.STRING),),
        (Row(("k", "v"), 0),),
    )
    assert evaluate_decision_table(t, {"f": "k"})["o"] == "v"
    assert evaluate_decision_table(t, {"f": "nope"}) is None


def _dt_agg(hp: HitPolicy, rows: tuple[Row, ...]) -> DecisionTable:
    return DecisionTable(
        "agg",
        hp,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (OutputColumn("o", "o", ColumnType.INT),),
        rows,
    )


def test_collect_sum_min_max_count_single_output() -> None:
    rows = (Row((1, 10), 0), Row((1, 30), 0), Row((1, 20), 0))
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_SUM, rows), {"f": 1}) == {"o": 60}
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_MIN, rows), {"f": 1}) == {"o": 10}
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_MAX, rows), {"f": 1}) == {"o": 30}
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_COUNT, rows), {"f": 1}) == {"o": 3}


def test_collect_sum_single_match_no_rows_and_zero() -> None:
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_SUM, (Row((1, 7), 0),)), {"f": 1}) == {"o": 7}
    assert evaluate_decision_table(_dt_agg(HitPolicy.COLLECT_SUM, (Row((1, 0), 0),)), {"f": 1}) == {"o": 0}
    t0 = DecisionTable(
        "z",
        HitPolicy.COLLECT_SUM,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (OutputColumn("o", "o", ColumnType.INT),),
        (),
    )
    assert evaluate_decision_table(t0, {"f": 1}) is None


def test_collect_sum_non_numeric_raises() -> None:
    t = _dt_agg(HitPolicy.COLLECT_SUM, (Row((1, 1), 0), Row((1, "x"), 0)))
    with pytest.raises(CollectAggregateError, match="aggregate"):
        evaluate_decision_table(t, {"f": 1})


def test_collect_sum_rejects_bool_even_if_int_subclass() -> None:
    t = _dt_agg(HitPolicy.COLLECT_SUM, (Row((1, True), 0), Row((1, 2), 0)))
    with pytest.raises(CollectAggregateError, match="aggregate"):
        evaluate_decision_table(t, {"f": 1})


def test_collect_aggregate_multi_output_sum_per_column() -> None:
    rows = (
        Row((1, 10, 100), 0),
        Row((1, 20, 200), 0),
        Row((1, 30, 300), 0),
    )
    t = DecisionTable(
        "m",
        HitPolicy.COLLECT_SUM,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (OutputColumn("a", "a", ColumnType.INT), OutputColumn("b", "b", ColumnType.INT)),
        rows,
    )
    assert evaluate_decision_table(t, {"f": 1}) == {"a": 60, "b": 600}


def test_collect_aggregate_multi_output_count() -> None:
    t = DecisionTable(
        "mc",
        HitPolicy.COLLECT_COUNT,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (OutputColumn("x", "x", ColumnType.INT), OutputColumn("y", "y", ColumnType.INT)),
        (Row((1, 1, 2), 0), Row((1, 3, 4), 0)),
    )
    assert evaluate_decision_table(t, {"f": 1}) == {"x": 2, "y": 2}


def test_collect_aggregate_requires_at_least_one_output_column() -> None:
    t = DecisionTable(
        "empty_out",
        HitPolicy.COLLECT_SUM,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (),
        (Row((1,), 0),),
    )
    with pytest.raises(CollectAggregateError, match="at least one output"):
        evaluate_decision_table(t, {"f": 1})


def test_collect_aggregate_missing_output_cell_raises() -> None:
    t = DecisionTable(
        "x",
        HitPolicy.COLLECT_SUM,
        (InputColumn("i", "f", ColumnType.INT, "=="),),
        (OutputColumn("o", "o", ColumnType.INT),),
        (Row((1,), 0),),
    )
    with pytest.raises(CollectAggregateError, match="missing output"):
        evaluate_decision_table(t, {"f": 1})


def test_json_roundtrip_collect_aggregate_policies() -> None:
    t = _dt_agg(HitPolicy.COLLECT_SUM, (Row((1, 2), 0), Row((1, 3), 0)))
    t2 = dt_from_json(dt_to_json(t))
    assert t2.hit_policy == HitPolicy.COLLECT_SUM
    assert evaluate_decision_table(t2, {"f": 1}) == {"o": 5}
