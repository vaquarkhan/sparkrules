# Example DRL files

Each `.drl` here is **self-contained** for learning. **Sample rows** that match the
`when` patterns live in the matching `*_facts.json` files (same directory).

| DRL | Sample facts | Fact shape (Spark / `rows_from_session`) |
|-----|----------------|--------------------------------------------|
| [minimal.drl](minimal.drl) | [minimal_facts.json](minimal_facts.json) | Column `t`: struct with numeric field `x` (type `T` in DRL). |
| [discount_tier.drl](discount_tier.drl) | [discount_tier_facts.json](discount_tier_facts.json) | Column `txn`: struct `Transaction` with `amount`, `region`. |

**Spark:** load JSON with `json.loads`, build `rows_from_session(spark, rows)`, then
`SparkRuleExecutor.from_drl(drl_text).apply(df)` for typed V2 columns (Strategy A/B/C).
See [../spark/apply_drl_local.py](../spark/apply_drl_local.py).

**V1 JSON column:** `apply_drl(df, drl, use_v2=False)` still returns `out_json` per row;
default is **V2 typed columns** — prefer `SparkRuleExecutor` or `apply_drl(..., use_v2=True)`.
