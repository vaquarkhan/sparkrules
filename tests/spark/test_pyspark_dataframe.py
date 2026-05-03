from __future__ import annotations

import json

import pytest

pytest.importorskip("pyspark", reason="PySpark+JVM required for Spark tests")
from pyspark.sql import Row, SparkSession  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from sparkrules.spark import apply_drl, rows_from_session  # noqa: E402

pytestmark = pytest.mark.spark

_DRL = """
rule r1
when
$z : T ( $z.n == 1 )
then
result.x = 1;
end
"""


def _facts_struct_df(spark: SparkSession):
    """V2 ``SparkRuleExecutor`` rejects MapType facts — use an explicit StructType for ``z``."""

    schema = StructType(
        [
            StructField("id", StringType(), True),
            StructField("z", StructType([StructField("n", IntegerType(), True)]), True),
        ]
    )
    return spark.createDataFrame(
        [Row(id="1", z=Row(n=1)), Row(id="2", z=Row(n=0))],
        schema=schema,
    )


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    try:
        s = SparkSession.builder.master("local[1]").appName("sparkrules-e2e").getOrCreate()
    except (TypeError, OSError) as e:
        pytest.skip(f"Spark session unavailable: {e!s}")
    yield s
    s.stop()


def test_apply_drl_v2_typed_columns(spark: SparkSession) -> None:
    df0 = _facts_struct_df(spark)
    out = apply_drl(df0, _DRL, fact_id_field="id", use_v2=True)
    by_id = {r["id"]: r.asDict(recursive=True) for r in out.collect()}
    assert by_id["1"]["r_r1"] is True
    assert by_id["1"]["action_x"] == 1
    assert by_id["2"]["r_r1"] is False


def test_apply_drl_v1_json_path(spark: SparkSession) -> None:
    df0 = _facts_struct_df(spark)
    out = apply_drl(df0, _DRL, fact_id_field="id", use_v2=False)
    rows = {r.fact_id: (r.fired, r.out_json) for r in out.collect()}
    assert rows["1"][0] is True
    payload = json.loads(rows["1"][1])
    assert payload.get("action", {}).get("x") == 1
    assert rows["2"][0] is False


def test_rows_from_session_empty(spark: SparkSession) -> None:
    t = rows_from_session(spark, [])
    assert t.count() == 0
