# Quick Start

## Evaluate a rule

```python
from sparkrules.executor import RuleExecutor

drl = """
rule "high-value-order"
  salience 10
  reason_codes ["HV001"]
  when
    $order : Order( amount > 1000 )
  then
    result.risk = "high";
    result.review_required = true;
end
"""

result = RuleExecutor().run({"amount": 1500, "region": "US"}, drl)
print(result.fired)          # True
print(result.action_output)  # {'risk': 'high', 'review_required': True}
print(result.reason_codes)   # ('HV001',)
```

## Decision table

```python
from sparkrules.model.decision_table import (
    DecisionTable, InputColumn, OutputColumn, Row,
    ColumnType, HitPolicy, evaluate_decision_table,
)

dt = DecisionTable(
    name="discount",
    hit_policy=HitPolicy.FIRST,
    inputs=(InputColumn("tier", "customer_tier", ColumnType.STRING, "=="),),
    outputs=(OutputColumn("discount", "discount_pct", ColumnType.INT),),
    rows=(
        Row(("gold", 15), priority=0),
        Row(("silver", 5), priority=1),
    ),
)

result = evaluate_decision_table(dt, {"customer_tier": "gold"})
print(result)  # {'discount': 15}
```

## Start the API

```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --port 8042
```

Open http://127.0.0.1:8042/workbench/ for the browser-based Rules Workbench (**Overview** is the main dashboard). Optional Workbench login and default dev credentials **`admin` / `admin`** are documented in [WORKBENCH_LOGIN.md](WORKBENCH_LOGIN.md); without `SPARKRULES_WORKBENCH_AUTH`, no login screen appears.

## Adverse-action notice

```python
from sparkrules.executor import RuleExecutor, build_adverse_action_notice

executor = RuleExecutor()
rules = [credit_score_rule, income_rule, dti_rule]
results = [executor.run(applicant, drl) for drl in rules]

notice = build_adverse_action_notice(results, decision="decline", fact_id="app-123")
print(notice.principal_reasons)  # ('CR001', 'IN002', 'DTI003')
```

## Data profiling

```python
from sparkrules.dq import profile_rows

profile = profile_rows(batch_of_facts)
for f in profile.fields:
    print(f"{f.field_name}: {f.completeness:.0%} complete, {f.uniqueness:.0%} unique")
```

## Next steps

- [Full feature list](FEATURES.md)
- [Spark integration guide](SPARK_INTEGRATION.md)
- [Governance workflows](GOVERNANCE.md)
- [Jupyter notebooks](https://github.com/vaquarkhan/sparkrules/tree/main/examples/notebooks)
