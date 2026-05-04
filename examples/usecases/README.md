# Domain use-case examples

**Author:** Vaquar Khan  

Each subdirectory is a **self-contained SparkRules demo**: sample **DRL**, **CSV** tuned for that storyline, **`validate_csv.py`** (no JVM — uses `iter_rule_rows`), **`spark_e2e.py`** (PySpark + `SparkRuleExecutor.from_drl(drl).apply(df)` when Java is available; **V2** typed columns), and **`EXAMPLE.md`** with detailed rule explanations.

| Folder | Scenario | Narrative |
|--------|-----------|-----------|
| [clinical_research](clinical_research/) | Trial lab QC, dedupe chains, staged harmonization | [**EXAMPLE.md**](clinical_research/EXAMPLE.md) |
| [credit_card](credit_card/) | Issuer declines (MCC blocks, ledger, crypto/geo) | [**EXAMPLE.md**](credit_card/EXAMPLE.md) |
| [lending_portfolio](lending_portfolio/) | Drools-style underwriting (`App`), metadata demo | [**EXAMPLE.md**](lending_portfolio/EXAMPLE.md) |
| [point_of_sale](point_of_sale/) | Fraud + liquor compliance + cash vault + routing | [**EXAMPLE.md**](point_of_sale/EXAMPLE.md) |
| [reward_loyalty](reward_loyalty/) | Tier caps, premium partner lanes, balances | [**EXAMPLE.md**](reward_loyalty/EXAMPLE.md) |

Sample CSV files in each folder are part of these demos (**author:** Vaquar Khan).  

Generic PySpark scaffolding (minimal DRL loader, iterators) remains under [`../spark/`](../spark/).

Suggested order:

1. Pick a folder and run **`python examples/usecases/<name>/validate_csv.py`** from the repo root.
2. When Java + PySpark work: **`python examples/usecases/<name>/spark_e2e.py`**.
