"""Smoke: SparkRuleExecutor V2 strategies on ``local[1]`` (Req 6–8, Req 17)."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark", reason="PySpark+JVM required for Spark tests")
from pyspark.sql import Row, SparkSession  # noqa: E402
from pyspark.sql.types import IntegerType, StringType, StructField, StructType  # noqa: E402

from sparkrules.spark.executor import SparkRuleExecutor  # noqa: E402

pytestmark = pytest.mark.spark

_DRL = """
rule sql_hi salience 10 when $t : T ( $t.v == 1 ) then result.score = 7; end
rule sql_lo salience 1 when $t : T ( true ) then result.score = 3; end
rule py_re salience 0 when $t : T ( $t.name matches "(?=.*admin).*" ) then result.tag = "py"; end
"""


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    try:
        s = SparkSession.builder.master("local[1]").appName("sparkrules-v2-smoke").getOrCreate()
    except (TypeError, OSError) as e:
        pytest.skip(f"Spark session unavailable: {e!s}")
    yield s
    s.stop()


@pytest.fixture
def facts_df(spark: SparkSession):
    schema = StructType(
        [
            StructField("id", StringType(), True),
            StructField(
                "t",
                StructType(
                    [
                        StructField("v", IntegerType(), True),
                        StructField("name", StringType(), True),
                    ],
                ),
                True,
            ),
        ],
    )
    rows = [
        Row(id="a", t=Row(v=1, name="admin_user")),
        Row(id="b", t=Row(v=0, name="guest")),
    ]
    return spark.createDataFrame(rows, schema=schema)


def test_v2_strategies_smoke_sql_merge_and_python_fallback(spark: SparkSession, facts_df) -> None:
    ex = SparkRuleExecutor.from_drl(_DRL)
    out = ex.apply(facts_df)
    by_id = {r["id"]: r.asDict(recursive=True) for r in out.collect()}

    assert "r_sql_hi" in out.columns and "r_sql_lo" in out.columns and "r_py_re" in out.columns
    assert by_id["a"]["r_sql_hi"] is True and by_id["a"]["r_sql_lo"] is True
    assert by_id["a"]["r_py_re"] is True
    assert by_id["a"]["action_score"] == 7
    assert by_id["a"]["action_tag"] == "py"

    assert by_id["b"]["r_sql_hi"] is False and by_id["b"]["r_sql_lo"] is True
    assert by_id["b"]["r_py_re"] is False
    assert by_id["b"]["action_score"] == 3
    assert by_id["b"]["action_tag"] is None

    assert out.select("fired_any").filter("fired_any").count() == 2
