#!/usr/bin/env python3
# Author: Vaquar Khan
"""Loyalty rules + Spark (**V2** typed columns: ``r_*``, ``action_*``, ``fired_any``).

Nested member fact ``m`` is a Spark ``StructType`` via ``Row``.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def _rows(csv_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows.append(
                {
                    "redemption_ref": rec["redemption_ref"].strip(),
                    "m": {
                        "tier_code": rec["tier_code"].strip(),
                        "offer_category": rec["offer_category"].strip(),
                        "points_balance": int(rec["points_balance"] or "0"),
                        "redemption_points_requested": int(
                            rec["redemption_points_requested"] or "0"
                        ),
                        "account_lifecycle": rec["account_lifecycle"].strip(),
                    },
                }
            )
    return rows


def main() -> int:
    try:
        from pyspark.sql import Row, SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print('Install: pip install -e ".[test]"', file=sys.stderr)
        return 1

    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=_here() / "data" / "loyalty_sample.csv")
    p.add_argument("--partitions", type=int, default=4)
    args = p.parse_args()

    sd = _here()
    try:
        spark = SparkSession.builder.master("local[*]").appName("sparkrules-loyalty").getOrCreate()
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed: {e}", file=sys.stderr)
        return 1

    try:
        from sparkrules.spark.executor import SparkRuleExecutor

        drl = (sd / "loyalty_reward_rules.drl").read_text(encoding="utf-8")
        executor = SparkRuleExecutor.from_drl(drl)
        print("RulePack:", executor.rulepack.summary())

        spark_rows = [
            Row(redemption_ref=r["redemption_ref"], m=Row(**r["m"])) for r in _rows(args.csv)
        ]
        df_in = spark.createDataFrame(spark_rows).repartition(max(2, args.partitions))
        t0 = time.perf_counter()
        out = executor.apply(df_in)
        cnt = out.count()
        fired = out.filter(F.col("fired_any") == True).count()  # noqa: E712
        r_cols = [c for c in out.columns if c.startswith("r_")]
        print(
            f"rows={cnt}  fired_any={fired}  rule_cols={r_cols}  elapsed_s={time.perf_counter() - t0:.3f}"
        )
        out.printSchema()
        out.show(12, truncate=False)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
