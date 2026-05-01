# SparkRules

**The business rule engine that Python was missing.**

Drools-style DRL syntax, explainable decisions, regulatory-grade audit trails — from laptop to lakehouse, no JVM required.

## Quick install

```bash
pip install sparkrules          # core engine
pip install sparkrules[api]     # + FastAPI server and Workbench
pip install sparkrules[spark]   # + PySpark integration
pip install sparkrules[all]     # everything
```

## 30-second example

```python
from sparkrules.executor import RuleExecutor

result = RuleExecutor().run(
    {"amount": 1500, "region": "US"},
    'rule "high-value" when $f : Fact( amount > 1000 ) then result.risk = "high"; end',
)
print(result.fired)          # True
print(result.action_output)  # {'risk': 'high'}
```

## Key capabilities

- **Rule engine** — DRL syntax, decision tables, explainable outputs
- **API + Workbench** — FastAPI server with browser-based Monaco editor
- **Governance** — versioning, namespaces, dev→stage→prod promotion
- **Regulatory compliance** — adverse-action notices (ECOA/FCRA/GDPR)
- **Data quality** — built-in checks + statistical profiling
- **Spark integration** — optional, config-driven, multi-platform

## Next steps

- [Install guide](install.md)
- [Quick start tutorial](quickstart.md)
- [Full feature list](FEATURES.md)
- [Architecture](HOW_IT_WORKS.md)
