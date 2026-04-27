#!/usr/bin/env python3
"""Complex Drools-style DRL + PySpark: load CSV (or synthetic rows), nested fact `t`, apply_drl.

Demonstrates:
  - broadcast DRL + mapPartitions (through apply_drl)
  - repartitioning for parallelism on larger data
  - timing for throughput smoke (not a formal benchmark)

Prerequisites: Java, pip install -e ".[test]"

Examples:
  python examples/spark/campaign_e2e.py
  python examples/spark/campaign_e2e.py --synthetic 50000 --partitions 32
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _spark_dir() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print("Install: pip install -e \".[test]\"", file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(description="Campaign DRL + Spark DataFrame E2E")
    p.add_argument(
        "--csv",
        type=Path,
        default=_spark_dir() / "data" / "campaign_facts.csv",
        help="CSV with id,amount,risk_score,region,segment",
    )
    p.add_argument(
        "--synthetic",
        type=int,
        default=0,
        metavar="N",
        help="If >0, ignore CSV and generate N rows (deterministic mix of regions/amounts)",
    )
    p.add_argument("--partitions", type=int, default=8, help="Target RDD partitions after load")
    args = p.parse_args()

    try:
        spark = (
            SparkSession.builder.master("local[*]")
            .appName("sparkrules-campaign-e2e")
            .getOrCreate()
        )
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed (Java installed?): {e}", file=sys.stderr)
        return 1

    try:
        from sre.spark import apply_drl

        drl = (_spark_dir() / "drools_campaign.drl").read_text(encoding="utf-8")

        if args.synthetic > 0:
            n = args.synthetic
            base = spark.range(0, n).select(
                F.concat(F.lit("g-"), F.col("id").cast("string")).alias("id"),
                (F.lit(400.0) + (F.col("id") % F.lit(900)).cast("double")).alias("amount"),
                (F.col("id") % F.lit(101)).cast("int").alias("risk_score"),
                F.when((F.col("id") % F.lit(5)) < F.lit(2), F.lit("US"))
                .when((F.col("id") % F.lit(5)) == F.lit(2), F.lit("EU"))
                .otherwise(F.lit("APAC"))
                .alias("region"),
                F.lit("retail").alias("segment"),
            )
        else:
            if not args.csv.is_file():
                print(f"CSV not found: {args.csv}", file=sys.stderr)
                return 1
            base = spark.read.option("header", "true").option("inferSchema", "true").csv(
                str(args.csv)
            )
            base = base.select(
                F.col("id").cast("string"),
                F.col("amount").cast("double"),
                F.col("risk_score").cast("int"),
                F.col("region").cast("string"),
                F.col("segment").cast("string"),
            )

        df_in = base.select(
            "id",
            F.struct(
                F.col("amount"),
                F.col("risk_score"),
                F.col("region"),
                F.col("segment"),
            ).alias("t"),
        ).repartition(max(2, args.partitions))

        t0 = time.perf_counter()
        out = apply_drl(df_in, drl, fact_id_field="id")
        cnt = out.count()
        fired = out.filter(F.col("fired") == True).count()  # noqa: E712
        elapsed = time.perf_counter() - t0

        print(f"rows={cnt}  fired={fired}  elapsed_s={elapsed:.3f}  rows_per_s={cnt/elapsed:.0f}")
        print("sample:")
        out.show(5, truncate=False)
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
