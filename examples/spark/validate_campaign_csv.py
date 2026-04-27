#!/usr/bin/env python3
"""Validate drools_campaign.drl + campaign_facts.csv without Spark (pure Python).

Run from repo root:
  python examples/spark/validate_campaign_csv.py

Prints match count and sample JSON lines so CI / laptops without Java still get an E2E check.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _spark_dir() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    from sre.spark.dataframe import iter_rule_rows

    drl = (_spark_dir() / "drools_campaign.drl").read_text(encoding="utf-8")
    csv_path = _spark_dir() / "data" / "campaign_facts.csv"
    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for rec in r:
            rid = str(rec["id"])
            rows.append(
                {
                    "id": rid,
                    "t": {
                        "amount": float(rec["amount"]),
                        "risk_score": int(rec["risk_score"]),
                        "region": str(rec["region"]),
                        "segment": str(rec["segment"]),
                    },
                }
            )

    fired_n = 0
    for fact_id, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="id"):
        if fired:
            fired_n += 1
            if fired_n <= 3:
                d = json.loads(out_json)
                print(f"  match id={fact_id} tier={d.get('action', {}).get('tier')}")

    print(f"CSV rows={len(rows)}  rules_fired={fired_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
