#!/usr/bin/env python3
# Author: Vaquar Khan
"""POS checkout rules + Spark (**V2** typed columns: ``r_*``, ``action_*``, ``fired_any``).

Nested checkout fact ``t`` is built as a Spark ``StructType`` (``Row``), not a dict-backed ``MapType``.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def _rows(path: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            out.append(
                {
                    "txn_id": rec["txn_id"].strip(),
                    "t": {
                        "store_id": rec["store_id"].strip(),
                        "basket_cents": int(rec["basket_cents"] or "0"),
                        "payment_kind": rec["payment_kind"].strip(),
                        "risk_score": int(rec["risk_score"] or "0"),
                        "age_gate_item": int(rec["age_gate_item"] or "0"),
                        "id_verified": int(rec["id_verified"] or "0"),
                    },
                }
            )
    return out


def main() -> int:
    try:
        from pyspark.sql import Row, SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print('Install: pip install -e ".[test]"', file=sys.stderr)
        return 1

    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=_here() / "data" / "pos_checkout_sample.csv")
    p.add_argument("--partitions", type=int, default=4)
    args = p.parse_args()

    sd = _here()

    try:
        spark = SparkSession.builder.master("local[*]").appName("sparkrules-pos").getOrCreate()
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed: {e}", file=sys.stderr)
        return 1

    try:
        from sparkrules.compiler.rulepack import RulePack
        from sparkrules.spark import apply_drl

        drl = (sd / "pos_checkout_rules.drl").read_text(encoding="utf-8")
        print("RulePack:", RulePack.from_drl(drl).summary())

        spark_rows = [Row(txn_id=r["txn_id"], t=Row(**r["t"])) for r in _rows(args.csv)]
        df_in = spark.createDataFrame(spark_rows).repartition(max(2, args.partitions))

        t0 = time.perf_counter()
        out = apply_drl(df_in, drl, fact_id_field="txn_id", use_v2=True)
        cnt = out.count()
        fired = out.filter(F.col("fired_any") == True).count()  # noqa: E712
        elapsed = time.perf_counter() - t0
        r_cols = [c for c in out.columns if c.startswith("r_")]
        print(
            f"rows={cnt}  fired_any={fired}  rule_cols={r_cols}  "
            f"elapsed_s={elapsed:.3f}  rows_per_s={cnt / elapsed:.0f}"
        )
        out.printSchema()
        out.show(12, truncate=False)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
