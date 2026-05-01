from __future__ import annotations

import pytest

pytest.importorskip("pyspark", reason="PySpark required")
from pyspark.sql import Row  # noqa: E402

from sparkrules.spark import mpartition_rows  # noqa: E402

_DRL = "rule r when $x : T (1==1) then end"


def test_mpartition_rows_yields_rows() -> None:
    part = [Row(id="1", x=1)]
    out = list(mpartition_rows(part, _DRL, fact_id_field="id"))
    assert len(out) == 1
    assert out[0][0] == "1" and out[0][1] is True
