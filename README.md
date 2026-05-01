# sparkrules

**A Drools-style business rule engine for Python.** Define rules in DRL, evaluate facts, get explainable results — no JVM required.

<p align="center">
  <a href="https://pypi.org/project/sparkrules/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/sparkrules"></a>
  <a href="https://pypi.org/project/sparkrules/"><img alt="PyPI downloads" src="https://img.shields.io/pypi/dm/sparkrules"></a>
  <a href="https://github.com/vaquarkhan/sparkrules/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/vaquarkhan/sparkrules/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/vaquarkhan/sparkrules/actions/workflows/docker-publish.yml"><img alt="Docker" src="https://github.com/vaquarkhan/sparkrules/actions/workflows/docker-publish.yml/badge.svg"></a>
  <a href="https://github.com/vaquarkhan/sparkrules/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg"></a>
</p>

```python
from sparkrules.executor import RuleExecutor

result = RuleExecutor().run(
    {"amount": 1500, "region": "US"},
    'rule "high-value" when $f : Fact( amount > 1000 ) then result.risk = "high"; end',
)
print(result.fired)          # True
print(result.action_output)  # {'risk': 'high'}
```

## Install

```bash
pip install sparkrules
```

## Why SparkRules?

- **No JVM, no Drools server** — pure Python rule engine with DRL syntax, decision tables, and explainable outputs
- **Production-ready API** — FastAPI service with a browser-based Rules Workbench (Monaco editor, LSP diagnostics, simulations)
- **Optional Spark integration** — scale to cluster DataFrames with `apply_drl()` when you need it, stay on pure Python when you don't
- **Governance built in** — versioned rules, namespace scoping, dev→stage→prod promotion, deprecation workflows
- **100% test coverage** — 521 tests, property-based testing with Hypothesis, enforced coverage gate

## Performance

The default API path runs pure Python (no Spark). Typical throughput on a single core:

| Scenario | Throughput |
|----------|-----------|
| Simple single-pattern rule | ~5,000-10,000 evals/sec |
| Multi-condition rules with actions | ~1,000-5,000 evals/sec |
| Full API round-trip (HTTP + parse + eval) | ~200-500 req/sec |

For higher throughput, use `apply_drl()` with PySpark to distribute evaluation across a cluster. See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for methodology and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for honest scope boundaries.

## Quick start (from source)

```bash
git clone https://github.com/vaquarkhan/sparkrules.git
cd sparkrules
python -m pip install -e ".[test]"
python -c "import sparkrules; print('ok', sparkrules.__version__)"
pytest tests/ -q
```

## Start the API + Workbench

```bash
pip install sparkrules
python -m uvicorn sparkrules.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

Then open:
- **OpenAPI docs:** http://127.0.0.1:8042/docs
- **Rules Workbench:** http://127.0.0.1:8042/workbench/

Or use Docker:

```bash
docker compose up --build
# → http://127.0.0.1:8042/workbench/
```


## Feature highlights

### Rule authoring
- DRL-style `when` / `then` rule language with salience, agenda groups, activation groups
- Decision tables with hit policies: `UNIQUE`, `FIRST`, `PRIORITY`, `COLLECT`
- XLSX decision-table import/export
- Rule templates with placeholder substitution

### Execution
- Explainable outputs: bound fields, action outputs, reason codes
- Batch, two-pass, and streaming evaluation modes
- Deterministic replay with versioned rule snapshots
- Multi-pattern rules with local Cartesian expansion

### API and Workbench
- FastAPI with OpenAPI docs, health endpoint, rule CRUD, simulations
- **Rules Workbench** — browser UI with Monaco DRL editor, validate + LSP diagnostics, simulation, deployment readout
- Shadow, coverage, counterfactual, and chain simulation modes
- Time-travel debug capture and replay
- Data quality checks (not-null, range, in-set)

### Governance
- Versioned metadata store (in-memory, DuckDB, Iceberg, Postgres backends)
- Rule namespaces for multi-project scoping
- Dev → stage → prod promotion pins
- Deprecation workflow: propose, approve, enforce

### Spark integration (optional)
- `apply_drl(df, drl)` for cluster DataFrame evaluation via `mapPartitions`
- Pure Python by default — Spark is opt-in, not required
- Platform config: local, AWS Glue, Databricks, GCP Dataproc, Azure Synapse

> **Spark vs Python:** the API and Workbench run pure Python. For cluster-scale evaluation, see [docs/SPARK_INTEGRATION.md](docs/SPARK_INTEGRATION.md).

## How it works

![SparkRules flow](docs/images/sparrule-flow2.png)

1. Author rules in DRL or decision-table form
2. Parse and validate rule syntax
3. Evaluate facts and produce explainable results
4. Version, replay, and govern rule lifecycle

Architecture details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Use cases

- POS end-of-day decisioning
- Streaming authorization logic
- Settlement replay and correction
- Underwriting decision support
- Clinical trial eligibility screening

Details: [docs/USE_CASES.md](docs/USE_CASES.md) · Examples: [examples/](examples/README.md)

## API key (optional)

Set `SPARKRULES_API_KEY` to require authentication on mutating endpoints and sensitive GETs. Public without key: `/health`, OpenAPI, Workbench static shell. See [API run details](#start-the-api--workbench).

## Documentation

| Topic | Link |
|-------|------|
| Features | [docs/FEATURES.md](docs/FEATURES.md) |
| Architecture | [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) |
| Developer guide | [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) |
| Use cases | [docs/USE_CASES.md](docs/USE_CASES.md) |
| Spark integration | [docs/SPARK_INTEGRATION.md](docs/SPARK_INTEGRATION.md) |
| Governance | [docs/GOVERNANCE.md](docs/GOVERNANCE.md) |
| Benchmarks | [docs/BENCHMARKS.md](docs/BENCHMARKS.md) |
| Known limitations | [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Publishing / CI | [docs/PUBLISHING.md](docs/PUBLISHING.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

Copyright 2026 Vaquar Khan. See [CITATION.cff](CITATION.cff) for citation details.
