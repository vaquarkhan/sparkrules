# Drools-style features in the lending example

The file [**drools_lending_premium.drl**](drools_lending_premium.drl) is written to look like **Drools** / DRL that practitioners recognize.

| Feature | In this example | Notes |
|---------|-----------------|--------|
| **`rule` name** | `LendingPrimeRate2026` | Parsed and evaluated. |
| **`salience`** | `80` | Stored on `RuleAst`; **single-rule** `evaluate_rule` does not compete with other rules. For **ordering many rules**, use **`RuleSimulator.run_chain`** or **`POST /simulations/chain`**. |
| **`agenda_group`**, **`activation_group`** | `underwriting`, `retail_2026` | Parsed; single-rule eval ignores **agenda** ordering. |
| **`reason_codes`** | `[ "CREDIT", "CAPACITY", "COMPLIANCE" ]` | Parsed on the rule. |
| **`stop_on_fire`** | `true` | Parsed; effect is with **multi-rule chains**, not one rule in `apply_drl`. |
| **`when` / `then`** | Nested fact `$a : App ( ... $a.product in [ ... ] ... $a.state not in [ ... ] )` | **Core** semantics — **this** is what Spark partitions evaluate per row. |
| **Boolean logic** | `and`, `or`, `in` / `not in`, comparisons | Evaluated in `evaluate_rule`. |
| **`then` → `result.*`** | `result.tier`, `result.rate_class`, `result.program_id` | Written to `action_output` in JSON. |

**What full Drools parity adds (not in `apply_drl` alone)**

- **Rete / PHREAK**, **rule flow-group** across many rules: use the **chain simulator** or REST **chain** endpoint.
- **Truth maintenance**, **CEP windows**: not in this repo’s DRL subset.

**Performance on huge data**

- `apply_drl` = **broadcast** DRL + **`mapPartitions`** → parse **once per partition**, evaluate per row.
- Scale out with **more partitions**, **larger clusters**, and Spark tuning (AQE, shuffle). The `--synthetic` and `--partitions` flags in [**lending_e2e.py**](lending_e2e.py) are a **smoke** for throughput; production jobs set resources in **Glue / Databricks / Dataproc** (see `EngineConfig` in `src/sre/runtime/config_contract.py` and [deploy/README.md](../../deploy/README.md)).
