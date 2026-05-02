from __future__ import annotations

import pytest

pytest.importorskip("pyspark", reason="PySpark+JVM required for Spark tests")
from pyspark.sql import SparkSession  # noqa: E402

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


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    try:
        s = SparkSession.builder.master("local[1]").appName("sparkrules-e2e").getOrCreate()
    except (TypeError, OSError) as e:
        pytest.skip(f"Spark session unavailable: {e!s}")
    yield s
    s.stop()


def test_apply_drl_fires_on_rows(spark: SparkSession) -> None:
    base = [
        {"id": "1", "z": {"n": 1}},
        {"id": "2", "z": {"n": 0}},
    ]
    df0 = rows_from_session(spark, base)
    out = apply_drl(df0, _DRL, fact_id_field="id", use_v2=False)
    rows = {r.fact_id: (r.fired, r.out_json) for r in out.collect()}
    assert rows["1"][0] is True
    assert '"1"' in rows["1"][1] or "1" in rows["1"][1]
    assert rows["2"][0] is False


def test_rows_from_session_empty(spark: SparkSession) -> None:
    t = rows_from_session(spark, [])
    assert t.count() == 0
