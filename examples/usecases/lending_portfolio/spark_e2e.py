#!/usr/bin/env python3
# Author: Vaquar Khan
"""Lending prime tier DRL + Spark (same behavior as legacy ``lending_e2e``)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print('Install: pip install -e ".[test]"', file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(description="Lending DRL + Spark")
    p.add_argument("--csv", type=Path, default=_here() / "data" / "sample.csv")
    p.add_argument(
        "--synthetic",
        type=int,
        default=0,
        metavar="N",
        help="If >0, ignore CSV and generate N rows",
    )
    p.add_argument("--partitions", type=int, default=8)
    args = p.parse_args()

    try:
        spark = (
            SparkSession.builder.master("local[*]")
            .appName("sparkrules-lending-portfolio")
            .getOrCreate()
        )
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed (Java installed?): {e}", file=sys.stderr)
        return 1

    try:
        from sparkrules.spark import apply_drl

        sd = _here()
        drl = (sd / "drools_lending_premium.drl").read_text(encoding="utf-8")

        if args.synthetic > 0:
            n = args.synthetic
            sid = F.col("id")
            us = [
                "CA", "TX", "FL", "NY", "IL", "PA", "WA", "CO", "MA", "OR",
                "UT", "CT", "NJ", "MS", "NV", "OH", "GA", "AZ", "TN", "SC",
            ]
            st = F.element_at(
                F.array(*[F.lit(s) for s in us]),
                (sid % F.lit(len(us))).cast("int") + 1,
            )
            prods = ["PERSONAL_LOAN", "AUTO_REFI", "CREDIT_CARD", "HOME_EQUITY"]
            pr = F.element_at(
                F.array(*[F.lit(p) for p in prods]),
                (sid % F.lit(4)).cast("int") + 1,
            )
            base = spark.range(0, n).select(
                F.concat(F.lit("s-"), F.col("id").cast("string")).alias("id"),
                (F.lit(50_000) + (F.col("id") % F.lit(200_000)).cast("long")).alias(
                    "annual_income"
                ),
                (F.lit(600) + (F.col("id") % F.lit(200)).cast("int")).alias("fico_score"),
                (F.lit(0.22) + (F.col("id") % F.lit(30)).cast("double") * F.lit(0.01)).alias(
                    "dti"
                ),
                st.alias("state"),
                pr.alias("product"),
                (F.col("id") % F.lit(3)).cast("int").alias("delinq_90d_12m"),
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
                F.col("annual_income").cast("long"),
                F.col("fico_score").cast("int"),
                F.col("dti").cast("double"),
                F.col("state").cast("string"),
                F.col("product").cast("string"),
                F.col("delinq_90d_12m").cast("int"),
            )

        df_in = base.select(
            "id",
            F.struct(
                F.col("annual_income"),
                F.col("fico_score"),
                F.col("dti"),
                F.col("state"),
                F.col("product"),
                F.col("delinq_90d_12m"),
            ).alias("a"),
        ).repartition(max(2, args.partitions))

        t0 = time.perf_counter()
        out = apply_drl(df_in, drl, fact_id_field="id")
        cnt = out.count()
        fired = out.filter(F.col("fired") == True).count()  # noqa: E712
        elapsed = time.perf_counter() - t0

        print(
            f"rows={cnt}  fired={fired}  elapsed_s={elapsed:.3f}  rows_per_s={cnt/elapsed:.0f}"
        )
        out.show(5, truncate=False)
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
