#!/usr/bin/env python3
# Author: Vaquar Khan
"""PySpark local session + **V2** ``SparkRuleExecutor`` (typed columns, Strategy A/B/C).

This is the recommended Spark path: rules compile once, Catalyst runs Strategy A where
possible, and results are **typed columns** (``r_<rule>``, ``action_*``, ``fired_any``) —
not a JSON string column.

Prerequisites:
  - Java 17+ (or 11+) on PATH for Spark
  - ``pip install -e ".[test]"`` from the sparkrules repo root (brings in PySpark)

Run from repo root::

    python examples/spark/apply_drl_local.py
    python examples/spark/apply_drl_local.py --example discount
    python examples/spark/apply_drl_local.py --explain

Facts are loaded from ``examples/drl/*_facts.json`` (see ``examples/drl/README.md``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_bundle(example: str) -> tuple[str, list[dict]]:
    drl_dir = _repo_root() / "examples" / "drl"
    if example == "minimal":
        drl = (drl_dir / "minimal.drl").read_text(encoding="utf-8")
        facts = json.loads((drl_dir / "minimal_facts.json").read_text(encoding="utf-8"))
        return drl, facts
    if example == "discount":
        drl = (drl_dir / "discount_tier.drl").read_text(encoding="utf-8")
        facts = json.loads((drl_dir / "discount_tier_facts.json").read_text(encoding="utf-8"))
        return drl, facts
    raise ValueError(example)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--example",
        choices=("minimal", "discount"),
        default="minimal",
        help="Which bundled DRL + sample facts to run",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="Print extended Catalyst plan for the first rule column (Strategy A visibility)",
    )
    args = p.parse_args()

    try:
        from pyspark.sql import SparkSession
    except ImportError as e:
        print(
            'PySpark is not installed. From repo root: python -m pip install -e ".[test]"',
            file=sys.stderr,
        )
        print(e, file=sys.stderr)
        return 1

    try:
        spark = (
            SparkSession.builder.master("local[2]")
            .appName("sparkrules-examples-v2-executor")
            .getOrCreate()
        )
    except Exception as e:  # noqa: BLE001
        print(
            "Could not start SparkSession. Install a JRE/JDK and set JAVA_HOME if needed.\n"
            f"Error: {e}",
            file=sys.stderr,
        )
        return 1

    try:
        from sparkrules.compiler.rulepack import RulePack
        from sparkrules.spark.executor import SparkRuleExecutor
        from sparkrules.spark.dataframe import rows_from_session

        drl, table = _load_bundle(args.example)
        pack = RulePack.from_drl(drl)
        print("RulePack summary:", pack.summary())
        for row in pack.debug_classification():
            print(f"  {row['rule']}: {row['strategy']} — {row['classification_rationale']}")

        base = rows_from_session(spark, table)
        print("\nInput rows:")
        base.printSchema()
        base.show(truncate=False)

        executor = SparkRuleExecutor.from_drl(drl)
        out = executor.apply(base)
        print(
            "\nOutput (typed V2 columns; Strategy A uses Catalyst where classified SQL_PUSHDOWN):"
        )
        out.printSchema()
        out.show(truncate=False)

        r_cols = [c for c in out.columns if c.startswith("r_")]
        if args.explain and r_cols:
            print(f"\nExtended plan for `{r_cols[0]}` (rule fired boolean):")
            out.select(r_cols[0]).explain("extended")
    finally:
        spark.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
