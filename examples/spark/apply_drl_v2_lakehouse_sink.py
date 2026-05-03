#!/usr/bin/env python3
# Author: Vaquar Khan
"""PySpark **V2** rule scoring + ``create_result_sink`` (iceberg / delta / hudi / parquet).

This is the closest OSS-local analogue to “Databricks + lakehouse write”:

1. ``SparkRuleExecutor.apply`` emits typed columns (``r_*``, ``action_*``, ``fired_any``).
2. Rows are collected and written via :func:`sparkrules.runtime.create_result_sink`.

**Important:** ``create_result_sink`` persists JSON snapshots under ``out_dir`` (one file per
format label). On a real cluster you replace this with Iceberg/Delta/Hudi table writes
using the same row dictionaries (see ``docs/SPARK_INTEGRATION.md``).

Prerequisites: JRE on PATH, ``pip install -e ".[test]"`` from repo root.

Run::

    python examples/spark/apply_drl_v2_lakehouse_sink.py
    python examples/spark/apply_drl_v2_lakehouse_sink.py --out-dir ./build/sparkrules_sink_demo
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_minimal_bundle() -> tuple[str, list[dict[str, object]]]:
    drl_dir = _repo_root() / "examples" / "drl"
    drl = (drl_dir / "minimal.drl").read_text(encoding="utf-8")
    facts = json.loads((drl_dir / "minimal_facts.json").read_text(encoding="utf-8"))
    return drl, facts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for sink JSON files (default: temp dir under repo)",
    )
    args = p.parse_args()

    try:
        from pyspark.sql import SparkSession
    except ImportError:
        print('Install PySpark: pip install -e ".[test]"', file=sys.stderr)
        return 1

    out_root = args.out_dir or Path(tempfile.mkdtemp(prefix="sparkrules_sink_", dir=_repo_root()))

    try:
        spark = SparkSession.builder.master("local[2]").appName("sparkrules-v2-sink").getOrCreate()
    except Exception as e:  # noqa: BLE001
        print(f"SparkSession failed: {e}", file=sys.stderr)
        return 1

    try:
        from sparkrules.spark.dataframe import rows_from_session
        from sparkrules.spark.executor import SparkRuleExecutor
        from sparkrules.runtime import create_result_sink

        drl, table = _load_minimal_bundle()
        base = rows_from_session(spark, table)
        executor = SparkRuleExecutor.from_drl(drl)
        scored = executor.apply(base)
        rows = [r.asDict(recursive=True) for r in scored.collect()]
        print(f"Collected {len(rows)} scored row(s); writing sinks under {out_root.resolve()}")
        for fmt in ("iceberg", "delta", "hudi", "parquet"):
            sink = create_result_sink(fmt, out_dir=str(out_root / fmt))
            meta = sink.write(rows)
            print(f"  {fmt}: snapshot_id={meta.snapshot_id[:16]}...")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
