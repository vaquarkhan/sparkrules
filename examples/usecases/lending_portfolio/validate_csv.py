#!/usr/bin/env python3
# Author: Vaquar Khan
"""Validate ``drools_lending_premium.drl`` + ``data/sample.csv`` without Spark."""

from __future__ import annotations

import csv
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    import json

    from sparkrules.spark.dataframe import iter_rule_rows

    sd = _here()
    drl = (sd / "drools_lending_premium.drl").read_text(encoding="utf-8")
    csv_path = sd / "data" / "sample.csv"
    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows.append(
                {
                    "id": str(rec["id"]),
                    "a": {
                        "annual_income": int(rec["annual_income"]),
                        "fico_score": int(rec["fico_score"]),
                        "dti": float(rec["dti"]),
                        "state": str(rec["state"]),
                        "product": str(rec["product"]),
                        "delinq_90d_12m": int(rec["delinq_90d_12m"]),
                    },
                }
            )

    fired_n = 0
    for fact_id, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="id"):
        if not fired:
            continue
        fired_n += 1
        d = json.loads(out_json)
        if fired_n <= 5:
            act = d.get("action") or {}
            print(
                f"  id={fact_id} tier={act.get('tier')} program_id={act.get('program_id')}"
            )

    print(f"CSV rows={len(rows)}  rules_fired={fired_n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
