from __future__ import annotations

import pytest

from sre.model import (
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
