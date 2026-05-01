"""Cover sparkrules.spark.dataframe without a JVM (mock SparkSession / RDD)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("pyspark")

from sparkrules.spark.dataframe import apply_drl, iter_rule_rows, rows_from_session


def test_apply_drl_with_mock_spark() -> None:
    drl = "rule r when $t : T ( true ) then end"

    out_df = MagicMock(name="out_df")
    part_rdd = MagicMock()

    def _map_parts(fn: object) -> MagicMock:
        part = [{"id": "i1"}]
        for _ in fn(part):
            pass
        return part_rdd

    mspark = MagicMock()
    mspark.createDataFrame.return_value = out_df
    msc = MagicMock()
    mb = MagicMock()
    mb.value = drl
    msc.broadcast.return_value = mb
    mspark.sparkContext = msc

    df = MagicMock()
    df.sparkSession = mspark
    df.rdd = MagicMock()
    df.rdd.mapPartitions = _map_parts

    res = apply_drl(df, drl)
    assert res is out_df
    mspark.createDataFrame.assert_called_once()


def test_iter_rule_rows_non_dict_partition_element() -> None:
    class _Seq:
        def __iter__(self) -> object:
            return iter((("id", "9"), ("k", 1)))

    drl = "rule r when $t : T ( true ) then end"
    rows = list(iter_rule_rows(iter([_Seq()]), drl))
    assert len(rows) == 1 and rows[0][0] == "9"


def test_rows_from_session_empty_and_nonempty() -> None:
    spark = MagicMock()
    spark.createDataFrame.side_effect = lambda rows, schema=None: (rows, schema)
    r0 = rows_from_session(spark, [])
    assert r0[0] == []

    r1 = rows_from_session(spark, [{"id": "1", "n": "a"}])
    assert r1[0] == [{"id": "1", "n": "a"}]
