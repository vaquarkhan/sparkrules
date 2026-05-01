#!/usr/bin/env python3
# Author: Vaquar Khan
"""Validate ``clinical_trials_rules.drl`` + ``data/sample.csv`` without Spark."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    sd = _here()
    if str(sd) not in sys.path:
        sys.path.insert(0, str(sd))

    from staging import flatten_for_iter
    from sparkrules.spark.dataframe import iter_rule_rows

    drl = (sd / "clinical_trials_rules.drl").read_text(encoding="utf-8")
    csv_path = sd / "data" / "sample.csv"
    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows.append(flatten_for_iter("record_id", dict(rec)))

    fired_n = 0
    for fact_id, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="record_id"):
        if not fired:
            continue
        d = json.loads(out_json)
        action = d.get("action") or {}
        fired_n += 1
        print(
            f"  {fact_id}  conversion_applied={action.get('conversion_applied')!r}  "
            f"dedup_policy={action.get('dedup_policy')!r}  "
            f"normalized_value={action.get('normalized_value')!r}"
        )

    print(f"CSV rows={len(rows)}  rules_fired={fired_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
