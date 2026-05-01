#!/usr/bin/env python3
# Author: Vaquar Khan
"""Validate loyalty DRL + CSV without Spark."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    from sparkrules.spark.dataframe import iter_rule_rows

    sd = _here()
    drl = (sd / "loyalty_reward_rules.drl").read_text(encoding="utf-8")
    csv_path = sd / "data" / "loyalty_sample.csv"
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows.append(
                {
                    "redemption_ref": rec["redemption_ref"].strip(),
                    "m": {
                        "tier_code": rec["tier_code"].strip(),
                        "offer_category": rec["offer_category"].strip(),
                        "points_balance": int(rec["points_balance"] or "0"),
                        "redemption_points_requested": int(
                            rec["redemption_points_requested"] or "0"
                        ),
                        "account_lifecycle": rec["account_lifecycle"].strip(),
                    },
                }
            )

    n = 0
    for fid, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="redemption_ref"):
        if not fired:
            continue
        n += 1
        act = json.loads(out_json).get("action") or {}
        print(
            f"  {fid}  reward_status={act.get('reward_status')!r}  reason={act.get('reason_code')!r}"
        )
    print(f"rows={len(rows)}  fired={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
