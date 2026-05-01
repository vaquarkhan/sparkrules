**Author:** Vaquar Khan  

## Credit card  -  authorization rails

Demonstrates issuer-side **risk + policy overlays** atop authorization payloads: issuer ledger checks, prohibited or high-risk MCC catalogs, cryptographic merchant cross-border pairings - before standard approvals.

### Fact shape (`c`)

Each **`auth`** row emits **`{ auth_id, c: { txn_amount_cents, available_credit_cents, account_status, mcc_raw, mcc_group, crypto_merchant, cross_border } }`**.

Statuses like **`SUSPENDED`** short-circuit approvals; **`mcc_raw`** aligns with Visa/MCI codes (simplified illustrative list).

### Rules (`card_auth_rules.drl`)

| Rule | Scenario | Typical interpretation |
|------|----------|-------------------------|
| **decline_account_suspended** (~120, sod) | Account lifecycle not active | Freeze further spend authorization. |
| **decline_high_risk_mcc** (~118, sod) | `mcc_group == "HIGH_RISK"` or raw code in `{7995,7922,...}` | Decline discretionary spend categories outright. |
| **decline_over_available_credit** (~116, sod) | Posting exceeds available revolving credit line | Equivalent to NSF on credit ledger. |
| **decline_crypto_cross_border** (~115, sod) | `crypto_merchant` + **`cross_border`** | Composite compliance signal (illustrative). |
| **approve_travel_bonus** (~60) | `mcc_group == "TRAVEL"` + active account + within limit | Specialized spend path with marketing coding `TRAVEL-ACCEL-PATH`. |
| **approve_daily_spend_standard** (~50) | Default approvals excluding travel overlaps | Adds `TRAVEL`-negative guard (`mcc_group != "TRAVEL"`) so mutually exclusive approvals do not collide. |

### Scripts

```bash
python examples/usecases/credit_card/validate_csv.py
python examples/usecases/credit_card/spark_e2e.py
```
