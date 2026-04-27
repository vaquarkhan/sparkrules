# sparkrules

SparkRules is a Drools-style business rule engine for Spark-oriented data workflows. It supports DRL authoring, decision-table authoring, explainable execution, deterministic replay patterns, and API integration for high-volume decisioning services.

Repository: https://github.com/vaquarkhan/sparkrules

## Feature catalog

### Rule authoring and modeling

- DRL-style `when` / `then` rule language
- Rule metadata: handle, version, group, salience, activation group, reason codes
- Rule template support with placeholder substitution and validation
- Decision table model with hit policies: `UNIQUE`, `FIRST`, `PRIORITY`, `COLLECT`
- Decision table JSON import/export helpers
- XLSX decision-table import
- XLSX decision-table export

### Parsing and execution semantics

- Parser and AST model for rule source
- Pretty-printer for normalized DRL output
- Expression support: comparisons, boolean logic, list membership, function calls, field paths
- Execution controls: salience ordering, agenda controls, activation-group behavior
- Explainable execution outputs (bound fields and action outputs)

### Compiler and runtime primitives

- Rule strategy classification
- Rule batching support
- Discrimination network structures
- Batch and two-pass runtime helper modules
- Streaming helper primitives (refresh and TTL checks)
- Derived-column cache utility
- Iceberg-like snapshot store for deterministic replay/testing workflows

### Metadata store and lifecycle

- In-memory versioned metadata store
- Active-window overlap detection
- Rule activation/deactivation
- Soft delete behavior
- Version listing and time-based resolution
- Active-set hashing

### Simulation and experimentation

- Rule simulator for pre-deployment checks
- Replay helper module
- A/B assignment primitives

### Spark and data-plane integration

- Spark partition iterators for rule-row evaluation
- DataFrame helper for DRL application flow
- Session row helper utilities

### API and connectivity

- FastAPI app factory
- Health endpoint
- Rule registration/listing endpoints
- Simulation endpoint
- Data-quality evaluation endpoint (`/dq/evaluate`)
- Lightweight client SDK
- In-process connect server dispatch module

### Data quality (Phase 2a in progress)

- DQ severity model (`WARN`, `ERROR`)
- DQ checks:
  - not-null
  - numeric range (between)
  - in-set
- API check parsing and validation
- Violation generation with code, field, message, and severity

### Observability

- Logging helper functions
- Metrics endpoint helpers

### Quality and reliability

- Unit tests
- Property tests
- Integration tests
- Optional perf tests
- 100% line coverage gate on `src/sre`

## How it works

1. Author rules in DRL or decision-table form.
2. Parse and validate rule source.
3. Compile/evaluate rules against fact payloads.
4. Return explainable outputs and runtime metadata.
5. Use replay and store versioning semantics for deterministic re-runs.

Read architecture details: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Use cases

- POS end-of-day decisioning
- Streaming authorization logic
- Settlement replay and correction
- Underwriting decision support

Details: [docs/USE_CASES.md](docs/USE_CASES.md)

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
