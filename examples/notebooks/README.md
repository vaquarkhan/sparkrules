# Jupyter Notebooks

Interactive examples for SparkRules. Open in Jupyter, VS Code, or view on GitHub.

| Notebook | Topic |
|----------|-------|
| [01_getting_started.ipynb](01_getting_started.ipynb) | Define rules in DRL, evaluate facts, inspect explainable results |
| [02_decision_tables.ipynb](02_decision_tables.ipynb) | Create decision tables, hit policies, evaluate and export |
| [03_api_simulation.ipynb](03_api_simulation.ipynb) | REST API: validate, simulate, counterfactual, governance |

## Setup

```bash
pip install sparkrules jupyter
jupyter notebook
```

For notebook 03 (API), start the server first:

```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --port 8042
```
