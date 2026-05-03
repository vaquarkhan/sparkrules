#!/usr/bin/env python3
# Author: Vaquar Khan
"""Clinical trial DRL + PySpark (**V2** typed columns; see EXAMPLE.md).

Facts use a nested ``StructType`` for ``f`` (not inferred ``MapType`` from Python dicts).
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    sd = _here()
    if str(sd) not in sys.path:
        sys.path.insert(0, str(sd))

    from staging import flatten_for_iter  # noqa: E402

    try:
        from pyspark.sql import Row, SparkSession
        from pyspark.sql import functions as F
    except ImportError:
        print('Install: pip install -e ".[test]"', file=sys.stderr)
        return 1

    p = argparse.ArgumentParser(description="Clinical research DRL + Spark")
    p.add_argument("--csv", type=Path, default=sd / "data" / "sample.csv")
    p.add_argument("--partitions", type=int, default=4)
    args = p.parse_args()

    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 1

    try:
        spark = (
            SparkSession.builder.master("local[*]")
            .appName("sparkrules-clinical-research")
            .getOrCreate()
        )
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed (Java installed?): {e}", file=sys.stderr)
        return 1

    try:
        from sparkrules.compiler.rulepack import RulePack
        from sparkrules.spark import apply_drl

        drl = (sd / "clinical_trials_rules.drl").read_text(encoding="utf-8")
        print("RulePack:", RulePack.from_drl(drl).summary())

        rows: list[dict[str, object]] = []
        with args.csv.open(encoding="utf-8", newline="") as fh:
            for rec in csv.DictReader(fh):
                rows.append(flatten_for_iter("record_id", dict(rec)))

        spark_rows = [Row(record_id=r["record_id"], f=Row(**r["f"])) for r in rows]
        df_in = spark.createDataFrame(spark_rows).repartition(max(2, args.partitions))

        t0 = time.perf_counter()
        out = apply_drl(df_in, drl, fact_id_field="record_id", use_v2=True)
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
