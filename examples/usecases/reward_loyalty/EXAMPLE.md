**Author:** Vaquar Khan  

## Reward / loyalty  -  earn & burn adjudication

The demo focuses on **tier-based guardrails**, not full earn math: freezes, redemption burst caps, differentiated experiences for GOLD vs PLATINUM portfolios, Bronze earn paths, insufficient balance handling.

### Fact shape (`m`)

Each **`redemption_ref`** emits **`{ redemption_ref, m: { tier_code, offer_category, points_balance, redemption_points_requested, account_lifecycle } }`**.

Statuses include **`ACTIVE`** versus **`FROZEN`** (marketing holds, AML/KYC freezes, suspected fraud tooling).

### Rules (`loyalty_reward_rules.drl`)

| Priority | Intent | Signals |
|---------|--------|---------|
| **deny_account_frozen** (~120, sod) | Issuer blocked profile | Lifecycle `FROZEN`. |
| **deny_insufficient_points** (~119, sod) | Ledger shortfall guard | Requests exceed balance. Must precede quota rules. |
| **deny_silver_burst_cap** (~118, sod) | Non-premium quotas | Monthly burn limit for **`SILVER`**. |
| **gold_dining_bonus_lane / platinum_partner_escalation** | Premium uplift partners | GOLD + `DINING`, PLATINUM + `AIRLINE`. |
| **silver_standard_catalog / bronze_baseline_grant** | Accessible tiers | Standard catalog unlocking + Bronze onboarding path. |
| **gold_catalog_non_dining** | Catch-all retail redemptions after dining exclusivity | GOLD + **`GENERAL_MERCH`**. |

`stop_on_fire` ensures compliance freezes and ledger denials preempt marketing bonuses - you would replicate that with BPM or microservice orchestrators.

### Scripts

```bash
python examples/usecases/reward_loyalty/validate_csv.py
python examples/usecases/reward_loyalty/spark_e2e.py
```
