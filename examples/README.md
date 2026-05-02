# Examples

## Quick start

```bash
pip install sparkrules[api]
```

## DRL rule files

| File | Domain | Features demonstrated |
|------|--------|---------------------|
| [drl/minimal.drl](drl/minimal.drl) | Basic | Simplest possible rule |
| [drl/discount_tier.drl](drl/discount_tier.drl) | Retail | Salience, AND conditions |
| [drl/credit_underwriting.drl](drl/credit_underwriting.drl) | Lending | Activation groups, reason codes, multi-rule pack |
| [drl/fraud_detection.drl](drl/fraud_detection.drl) | Payments | stop_on_fire, risk scoring, velocity checks |
| [drl/insurance_claims.drl](drl/insurance_claims.drl) | Insurance | Agenda groups, staged evaluation, claim routing |

## Python scripts

| Script | What it demonstrates |
|--------|---------------------|
| [python/evaluate_drl_file.py](python/evaluate_drl_file.py) | Load and evaluate a DRL file |
| [python/api_inprocess.py](python/api_inprocess.py) | In-process FastAPI app inspection |
| [python/v2_local_executor.py](python/v2_local_executor.py) | **V2 engine**: RulePack classification, alpha network, performance benchmarks |
| [python/adverse_action_demo.py](python/adverse_action_demo.py) | **Regulatory**: ECOA/FCRA adverse-action notice generation |
| [python/data_profiling_demo.py](python/data_profiling_demo.py) | **DQ**: Statistical profiling + quality checks before rule evaluation |
| [python/opa_export_demo.py](python/opa_export_demo.py) | **Policy**: Export DRL rules to OPA Rego format |

## Decision tables

| File | Format |
|------|--------|
| [decision_table/first_match.json](decision_table/first_match.json) | JSON decision table with FIRST hit policy |

## Jupyter notebooks

| Notebook | Topic |
|----------|-------|
| [notebooks/01_getting_started.ipynb](notebooks/01_getting_started.ipynb) | DRL rules, evaluation, explainable results |
| [notebooks/02_decision_tables.ipynb](notebooks/02_decision_tables.ipynb) | Decision tables, hit policies, JSON export |
| [notebooks/03_api_simulation.ipynb](notebooks/03_api_simulation.ipynb) | REST API: validate, simulate, counterfactual |

## Spark examples

| Script | What it demonstrates |
|--------|---------------------|
| [spark/apply_drl_local.py](spark/apply_drl_local.py) | PySpark `apply_drl()` on a local cluster |
| [spark/iter_rule_rows_no_jvm.py](spark/iter_rule_rows_no_jvm.py) | Pure-Python row iterator (no JVM needed) |

## End-to-end use cases

Complete domain examples with DRL rules, sample CSV data, validation scripts, and Spark E2E jobs:

| Use case | Domain | Files |
|----------|--------|-------|
| [usecases/lending_portfolio/](usecases/lending_portfolio/) | Lending | 50-rule underwriting pack, 90-row sample |
| [usecases/clinical_research/](usecases/clinical_research/) | Healthcare | Trial eligibility screening |
| [usecases/credit_card/](usecases/credit_card/) | Payments | Card authorization rules |
| [usecases/point_of_sale/](usecases/point_of_sale/) | Retail | POS checkout rules |
| [usecases/reward_loyalty/](usecases/reward_loyalty/) | Loyalty | Reward tier assignment |

## dbt integration

| Example | What it demonstrates |
|---------|---------------------|
| [dbt_clinical/](dbt_clinical/) | dbt + DuckDB staging for clinical lab data |
