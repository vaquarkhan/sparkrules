#!/usr/bin/env python3
# Author: Vaquar Khan
"""End-to-end: PySpark local session + sre.spark.apply_drl on a small DataFrame.

Prerequisites:
  - Java 17+ (or 11+, depending on your PySpark build) on PATH for Spark
  - pip install -e ".[test]"  (brings in pyspark) from the sparkrules repo root

Run from repo root:
  python examples/spark/apply_drl_local.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _drl() -> str:
    p = _repo_root() / "examples" / "drl" / "minimal.drl"
    return p.read_text(encoding="utf-8")


def main() -> int:
    try:
        from pyspark.sql import SparkSession
    except ImportError as e:
        print("PySpark is not installed. From repo root: python -m pip install -e \".[test]\"", file=sys.stderr)
        print(e, file=sys.stderr)
        return 1

    try:
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("sparkrules-examples-apply_drl")
            .getOrCreate()
        )
    except Exception as e:  # noqa: BLE001
        print(
            "Could not start SparkSession. Install a JRE/JDK and ensure JAVA_HOME is set if needed.\n"
            f"Error: {e}",
            file=sys.stderr,
        )
        return 1

    try:
        from sparkrules.spark import apply_drl, rows_from_session

        drl = _drl()
        # Two facts: first matches minimal.drl ($t.x == 1), second does not
        table = [
            {"id": "row-1", "t": {"x": 1}},
            {"id": "row-2", "t": {"x": 2}},
        ]
        base = rows_from_session(spark, table)
        print("Input rows:")
        base.show(truncate=False)

        out = apply_drl(base, drl, fact_id_field="id")
        print("Output (fact_id, fired, out_json):")
        out.show(truncate=False)

        for r in out.collect():
            payload = json.loads(r.out_json)
            print(
                f"  {r.fact_id}: fired={r.fired}  action={payload.get('action', {})}  bound={payload.get('bound', {})}"
            )
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
