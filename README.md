# sparkrules

SparkRules is a Drools-style business rule engine for Spark-oriented data workflows.
It supports rule authoring, rule execution, decision tables, simulation, and service integration for high-volume decisioning scenarios.

Repository: https://github.com/vaquarkhan/sparkrules

## Features

- DRL-style rule language with `when` / `then`
- Salience, agenda groups, activation groups, reason codes, and pass grouping
- Decision table support with JSON model and XLSX import/export
- Rule compiler with batching, strategy classification, and discrimination network support
- Stateful metadata store behavior (versioning, activation/deactivation, overlap checks)
- Replay-oriented runtime model with run metadata and snapshot semantics
- Simulation and A/B primitives
- FastAPI endpoints for health, rule operations, and simulations
- Spark dataframe helpers for partition evaluation and output shaping
- Logging and metrics helpers for observability

## How it works

1. Rules are authored in DRL-style syntax or decision-table form.
2. Rules are parsed and compiled into executable structures.
3. Facts are evaluated in rule-execution flows (single, batch, or Spark-assisted patterns).
4. Results include fired state, bound fields, and action outputs.
5. Runtime metadata enables deterministic replay and audit workflows.

Read full architecture flow in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## Use cases

- POS end-of-day rule evaluation with two-pass style flows
- Streaming authorization decisions
- Settlement replay and correction workflows
- Underwriting decisions with explainability data

Use-case details: [docs/USE_CASES.md](docs/USE_CASES.md).

## Quick start

```bash
git clone https://github.com/vaquarkhan/sparkrules.git
cd sparkrules
python -m pip install -e ".[test]"
python -c "import sre; print('ok', sre.__version__)"
pytest tests/ -q
```

Use the same interpreter for install and run commands.

## API run

```bash
uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs

## Documentation

| Topic | Link |
|------|------|
| Features and capability matrix | [docs/FEATURES.md](docs/FEATURES.md) |
| How the system works | [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) |
| Developer guide | [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) |
| Use cases | [docs/USE_CASES.md](docs/USE_CASES.md) |
| Examples | [examples/README.md](examples/README.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Citation metadata | [CITATION.cff](CITATION.cff) |

## License

[MIT](LICENSE)
