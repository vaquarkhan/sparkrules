# sparkrules

<p align="center">
  <a href="docs/images/sparkrules-logo.png">
    <img src="docs/images/sparkrules-logo.png" alt="SparkRules logo" width="520">
  </a>
</p>

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
- Streaming orchestration helper for micro-batch rule refresh
- Derived-column cache utility
- Iceberg-like snapshot store for deterministic replay/testing workflows
- Export service with manifest and SHA-256 integrity hash
- Output sink abstraction with format targets: `iceberg`, `delta`, `hudi`, `parquet`
- Input source contract validation for batch/stream profiles
- Zero-code-change configuration contract validation
- Spark target version normalization and validation (`3`, `3.x`, `3.x.y`)
- Platform switch by configuration only: `local`, `glue`, `databricks`, `gcp-dataproc`, `azure-synapse`
- Executor sizing controls: cores, workers, memory, Glue DPU
- Performance harness and scale evidence estimators
- UDF registry with version resolution and replay-time pinning semantics
- Guided template field schema generation for authoring surfaces

### Metadata store and lifecycle

- In-memory versioned metadata store
- Pluggable metadata backends: `in_memory`, `duckdb`, `iceberg`, `postgres`
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
- Runtime health diagnostics for UI payloads
- Automatic issue flags for slow stages, high shuffle, and failed tasks

### Quality and reliability

- Unit tests
- Property tests
- Integration tests
- Optional perf tests
- 100% line coverage gate on `src/sre`

## How it works

![SparkRules flow](docs/images/sparrule-flow.png)

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

**Windows (easiest):** double‑click `scripts\\dev_server.cmd` or run it from a terminal. By default the server uses **port 8042** (avoids clashes with other tools on 8000). Set `SPARKRULES_PORT=9000` before running the script to use another port.

**Any OS:**

```bash
python -m pip install -e "."
python -m uvicorn sre.api.app:create_app --factory --host 127.0.0.1 --port 8042
```

Open http://127.0.0.1:8042/docs

If the browser shows **connection refused**, the server is not running: keep the terminal open, use the **same port** in the URL, and use `http://` not `https://` unless you use a proxy.

## Rules Workbench (browser UI)

Drools Workbench–style **authoring and operations shell** (rule asset list, DRL validate, simulation, engine/deployment readout, template helper):

- http://127.0.0.1:8042/workbench/ (or the port you set in `SPARKRULES_PORT`)

The UI calls the same REST API (`/rules`, `/simulations`, `/system/deployment`, etc.).

**Phase 3 (started):** search and filter assets, download or import a **rule pack** JSON, and **compare two versions** of the same rule handle. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Docker

```bash
docker compose up --build
```

Then open http://127.0.0.1:8000/workbench/ and http://127.0.0.1:8000/docs (Dockerfile uses internal 8000; host port is whatever you map, e.g. `-p 8042:8000` then use **8042** in the browser.)

## Cloud deploy notes

High-level platform steps (Glue, Databricks, Dataproc, Synapse) and example JSON: [deploy/README.md](deploy/README.md).

## Documentation

| Topic | Link |
|------|------|
| Features and capability matrix | [docs/FEATURES.md](docs/FEATURES.md) |
| How the system works | [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) |
| Developer guide | [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) |
| Use cases | [docs/USE_CASES.md](docs/USE_CASES.md) |
| Scale and benchmarks (methodology) | [docs/BENCHMARKS.md](docs/BENCHMARKS.md) |
| Examples | [examples/README.md](examples/README.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Citation metadata | [CITATION.cff](CITATION.cff) |
| Roadmap (Phase 3 / 4) | [docs/ROADMAP.md](docs/ROADMAP.md) |

## License

SparkRules Non-Commercial Citation License 1.0.

- Citation is mandatory for use and redistribution.
- Commercial publishing/sale is not permitted without prior written permission.
- Full terms: [LICENSE](LICENSE)
