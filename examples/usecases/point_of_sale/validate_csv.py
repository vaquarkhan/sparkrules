#!/usr/bin/env python3
# Author: Vaquar Khan
"""Validate POS DRL + CSV without Spark."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def _here() -> Path:
    return Path(__file__).resolve().parent


def _row_dict(rec: dict[str, str]) -> dict[str, object]:
    return {
        "txn_id": rec["txn_id"].strip(),
        "t": {
            "store_id": rec["store_id"].strip(),
            "basket_cents": int(rec["basket_cents"] or "0"),
            "payment_kind": rec["payment_kind"].strip(),
            "risk_score": int(rec["risk_score"] or "0"),
            "age_gate_item": int(rec["age_gate_item"] or "0"),
            "id_verified": int(rec["id_verified"] or "0"),
        },
    }


def main() -> int:
    sd = _here()
    from sre.spark.dataframe import iter_rule_rows

    drl = (sd / "pos_checkout_rules.drl").read_text(encoding="utf-8")
    csv_path = sd / "data" / "pos_checkout_sample.csv"
    rows = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        rows = [_row_dict(dict(r)) for r in csv.DictReader(f)]

    n = 0
    for fid, fired, out_json in iter_rule_rows(iter(rows), drl, fact_id_field="txn_id"):
        if not fired:
            continue
        n += 1
        d = json.loads(out_json)
        act = d.get("action") or {}
        print(
            f"  {fid}  lane_outcome={act.get('lane_outcome')!r}  reason={act.get('reason_code')!r}"
        )
    print(f"rows={len(rows)}  fired={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
