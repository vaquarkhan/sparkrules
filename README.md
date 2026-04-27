# sparkrules

SparkRules is a Drools-style business rule engine for Spark-oriented data workflows.  
It provides DRL parsing, rule evaluation, decision-table support, simulation, replay-oriented data models, and API surfaces for rule operations.

Repository: [github.com/vaquarkhan/sparkrules](https://github.com/vaquarkhan/sparkrules)

## Product features

- DRL-style rules with `when` / `then`, salience, agenda group, activation group, reason codes, and pass grouping
- Decision table model (`UNIQUE`, `FIRST`, `PRIORITY`, `COLLECT`) with JSON serialization
- XLSX import/export utilities for decision tables
- Rule compiler package with batching, strategy classification, and discrimination network support
- Rule execution for single-fact and batch-oriented paths
- In-memory versioned metadata store with overlap checks, activation/deactivation, and active-set hashing
- Replay-ready runtime primitives (`run_id`, snapshot semantics, metadata store + iceberg-like table helpers)
- Simulation and A/B split primitives
- FastAPI app for health, rules, and simulation endpoints
- Spark dataframe helpers (`iter_rule_rows`, partition mapping, dataframe assembly)
- Observability utilities (logging + metrics endpoint helpers)

## Current quality gate

- Test command: `pytest tests/ -q`
- Coverage target: `src/sre` line coverage at 100%
- Current counts and gate details: [BUILD_STATUS.md](BUILD_STATUS.md)

## Quick start

```bash
git clone https://github.com/vaquarkhan/sparkrules.git
cd sparkrules
python -m pip install -e ".[test]"
python -c "import sre; print('ok', sre.__version__)"
pytest tests/ -q
```

Use the same interpreter for install and run commands (`python -m pip ...` then `python ...`).

## Run examples

- DRL and script examples: [examples/README.md](examples/README.md)
- Minimal parser smoke:

```bash
python -m sre.tools.smoke_drl
python -m sre.tools.smoke_drl examples/drl/minimal.drl
```

## API run (optional)

```bash
uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for OpenAPI.

## Documentation

| Topic | Link |
|------|------|
| Full requirements and glossary | [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) |
| Phase 1 status (done vs out-of-scope) | [docs/PHASE1_STATUS.md](docs/PHASE1_STATUS.md) |
| Documentation hub | [docs/README.md](docs/README.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Citation metadata | [CITATION.cff](CITATION.cff) |
| Roadmap blueprint | [idea-brainstrom.md](idea-brainstrom.md) |

## License

[MIT](LICENSE)
