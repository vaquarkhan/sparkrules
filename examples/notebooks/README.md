# Jupyter Notebooks

Interactive tutorials and use-case examples for SparkRules. Open in Jupyter, VS Code, or view on GitHub.

## Tutorials

| # | Notebook | What you'll learn |
|---|----------|-------------------|
| 01 | [Getting Started](01_getting_started.ipynb) | Define rules in DRL, evaluate facts, inspect explainable results, rule chains with salience ordering |
| 06 | [How SparkRules Works](06_how_sparkrules_works.ipynb) | **Complete architecture tutorial**: parsing, compilation, alpha network, execution strategies, governance |

## Use cases

| # | Notebook | Domain | Key features |
|---|----------|--------|-------------|
| 02 | [Decision Tables](02_decision_tables.ipynb) | General | Create tables with hit policies (FIRST, UNIQUE, PRIORITY, COLLECT), evaluate and export to JSON |
| 03 | [API & Simulation](03_api_simulation.ipynb) | General | REST API: validate DRL, simulate rules, counterfactual analysis, LSP diagnostics, governance |
| 04 | [Credit Underwriting](04_credit_underwriting.ipynb) | Lending | Multi-rule underwriting pack, activation groups, adverse-action notices (ECOA/FCRA), data profiling |
| 05 | [Fraud Detection](05_fraud_detection.ipynb) | Payments | Velocity checks, risk scoring, stop_on_fire, OPA Rego export for security review |

## Setup

```bash
pip install sparkrules jupyter
jupyter notebook
```

For notebook 03 (API & Simulation), start the server first:

```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --port 8042
```

## Recommended order

1. **06 - How SparkRules Works** - understand the architecture
2. **01 - Getting Started** - hands-on with DRL rules
3. **02 - Decision Tables** - spreadsheet-style rules
4. **04 - Credit Underwriting** - real-world lending pipeline
5. **05 - Fraud Detection** - real-time authorization rules
6. **03 - API & Simulation** - REST API and Workbench
