#!/usr/bin/env python3
# Author: Vaquar Khan
"""Loyalty rules + Spark."""

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
        from pyspark.sql import SparkSession
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
        from sre.spark import apply_drl

        drl = (sd / "loyalty_reward_rules.drl").read_text(encoding="utf-8")
        base = spark.createDataFrame(_rows(args.csv))
        df_in = base.select("redemption_ref", F.col("m")).repartition(max(2, args.partitions))
        t0 = time.perf_counter()
        out = apply_drl(df_in, drl, fact_id_field="redemption_ref")
        print(
            f"rows={out.count()}  fired="
            f"{out.filter(F.col('fired') == True).count()}  elapsed_s={time.perf_counter() - t0:.3f}"
        )
        out.show(12, truncate=False)
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
