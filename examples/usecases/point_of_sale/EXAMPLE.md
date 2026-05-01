**Author:** Vaquar Khan  

## Point of sale  -  checkout orchestration

This scenario routes **risk & compliance verdicts ahead of cashier UX hints**: synthetic fraud bursts, liquor/tobacco ID checks, unusually large cash tenders, NFC wallet adoption, boutique gift-card handling - all within one JSON-friendly fact keyed by **`txn_id`**.

### Fact shape (`t`)

Each row emits **`{ txn_id, t: { store_id, basket_cents, payment_kind, risk_score, age_gate_item, id_verified } }`**.

Integers are expressed as primitives so Spark structs infer cleanly; enums such as **`payment_kind`** are strings (`CARD`, `CASH`, `E_WALLET`, `GIFT_CARD`).

### Rules (`pos_checkout_rules.drl`)

Ordered by **salience** (evaluate top-to-bottom):

| Rule | When | Result |
|------|------|--------|
| **deny_synthetic_risk** (110, sod) | `risk_score >= 94` | Hard decline with **`RF-SYNTH-HIGH`**. Chain stops (`stop_on_fire`). |
| **deny_age_gate** (105, sod) | `age_gate_item == 1` and `id_verified == 0` | Tobacco/liquor without scan → **`AGE-ID-REQUIRED`**. |
| **supervisor_cash_floor** (95, sod) | `CASH` + `>= $1000` **`basket_cents`** gate | Locks lane for supervisory cash handling. |
| **approve_card_express** (60) | `CARD`, small baskets, tame risk scores | **`APPROVE_CONTACTLESS`**. |
| **approve_wallet_instant** (58) | `E_WALLET` + moderate fraud | NFC wallet fast-lane approvals. |
| **approve_cash_register** (50) | `CASH` under vault threshold | Standard register completions. |
| **approve_value_desk** (46) | `CARD` luxury basket | Sends shoppers to concierge / value desks. |
| **gift_card_escalation** (40) | `GIFT_CARD` payment | Specialized voucher handling workflows. |

`stop_on_fire` encodes irreversible cashier decisions - you would wire those into POS peripherals or queue managers.

### Scripts

```bash
python examples/usecases/point_of_sale/validate_csv.py
python examples/usecases/point_of_sale/spark_e2e.py
```
