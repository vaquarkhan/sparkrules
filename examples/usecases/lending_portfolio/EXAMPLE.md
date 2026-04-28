**Author:** Vaquar Khan  

## Lending portfolio — prime underwriting tier

A single underwriting rule expresses **composite retail policy**: credit (`fico`), capacity (`dti`, `annual_income`), behaviors (`delinq_90d_12m`), product whitelist, geography blacklist, orchestrated with Drools metadata that SparkRules parses even when only **one rule** fires per invocation.

### Fact shape (`a`)

Facts mirror a pseudo-`App` object: **`{ id, a: { annual_income, fico_score, dti, state, product, delinq_90d_12m } }`**.

Because this file is authored as **`rule LendingPrimeRate2026`** with **one `when`** block it exercises `parse(...)`, whereas multi-rule packs elsewhere call `parse_rules(...)`.

### Rule highlights (`drools_lending_premium.drl`)

| Metadata | Meaning here |
|-----------|---------------|
| **`salience 80`** | Ordering hook for future chaining; single-rule eval still parses it faithfully. |
| **`agenda_group "underwriting"`** | Names the decision agenda owning the underwriting decision. |
| **`activation_group "retail_2026"`** | Shows how Drools modeled mutual exclusion between campaigns. |
| **`reason_codes [ "CREDIT", "CAPACITY", "COMPLIANCE" ]`** | Mirrors explainability payloads you might surface downstream. |
| **`stop_on_fire true`** | Demonstrates authoring discipline for chain execution (see `spark/DROOLS_FEATURES.md`). |

`then` actions write **`result.tier`**, **`result.rate_class`**, **`result.program_id`**, surfaced in **`iter_rule_rows` JSON**.

### Scripts

```bash
python examples/usecases/lending_portfolio/validate_csv.py
python examples/usecases/lending_portfolio/spark_e2e.py --synthetic 50000 --partitions 24
```

Sample CSV **`data/sample.csv`** is the former `lending_portfolio_sample.csv` relocated here.
