#!/usr/bin/env python3
"""No JVM: the same DRL and facts through iter_rule_rows (used inside Spark mapPartitions).

Use this in CI or on machines without Java to verify the rule + row mapping logic.
The distributed path uses this iterator per partition; see apply_drl_local.py for full Spark.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _drl() -> str:
    return (_repo_root() / "examples" / "drl" / "minimal.drl").read_text(encoding="utf-8")


def main() -> int:
    from sre.spark.dataframe import iter_rule_rows

    drl = _drl()
    part = [
        {"id": "row-1", "t": {"x": 1}},
        {"id": "row-2", "t": {"x": 2}},
    ]
    for fact_id, fired, out_json in iter_rule_rows(iter(part), drl, fact_id_field="id"):
        d = json.loads(out_json)
        print(f"{fact_id}  fired={fired}  {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
