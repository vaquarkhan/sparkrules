#!/usr/bin/env python3
# Author: Vaquar Khan
"""Validate card auth DRL + CSV without Spark."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def main() -> int:
    from sparkrules.spark.dataframe import iter_rule_rows

    sd = _here()
    drl = (sd / "card_auth_rules.drl").read_text(encoding="utf-8")
    csv_path = sd / "data" / "card_auth_sample.csv"
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for rec in csv.DictReader(f):
            rows.append(
                {
                    "auth_id": rec["auth_id"].strip(),
                    "c": {
                        "txn_amount_cents": int(rec["txn_amount_cents"] or "0"),
                        "available_credit_cents": int(rec["available_credit_cents"] or "0"),
                        "account_status": rec["account_status"].strip(),
                        "mcc_raw": rec["mcc_raw"].strip(),
                        "mcc_group": rec["mcc_group"].strip(),
                        "crypto_merchant": int(rec["crypto_merchant"] or "0"),
                        "cross_border": int(rec["cross_border"] or "0"),
                    },
                }
            )

    n = 0
    for fid, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="auth_id"):
        if not fired:
            continue
        n += 1
        act = json.loads(out_json).get("action") or {}
        print(f"  {fid}  decision={act.get('decision')!r}  reason={act.get('reason_code')!r}")
    print(f"rows={len(rows)}  fired={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
