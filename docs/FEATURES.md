# Features

## Core engine

- DRL-style rule parsing and evaluation
- Salience-based priority control
- Agenda group and activation group execution controls
- Explainable outputs with bound data and reason codes
- Optional `SQL_JOIN` / multi-pattern path: for **list-valued** fact bindings, **local** execution can form a **Cartesian** product and take the first firing combination (not a distributed join unless wired with Spark)

## Authoring formats

- DRL text
- Decision table JSON model
- XLSX decision table import/export
- Template-driven guided field schema generation for UI/editor surfaces

## Execution and runtime

- Single-fact and batch-style execution paths
- Spark dataframe helper paths for partition processing - **optional**; default API path is pure Python ([SPARK_INTEGRATION.md](SPARK_INTEGRATION.md))
- Replay metadata model for deterministic re-runs
- Spark version targeting for Spark 3.x runtimes with normalization (`3`, `3.5`, `3.5.1`)
- Config-only platform switching across Glue/Databricks/GCP Dataproc/Azure Synapse/local
- Configurable executor resources (cores, workers, memory, Glue DPU)
- Streaming rule refresh orchestration for micro-batch pipelines
- Input-source contract validation (batch and streaming profiles)
- Format policy classification for supported source types
- Output sink abstraction with `iceberg`/`delta`/`hudi`/`parquet` targets
- Export service with manifest and SHA-256 output integrity hash
- Zero-code-change runtime configuration contract validation
- Performance harness and scale evidence estimation utilities
- UDF registry with versioned resolution and replay-time pinning

## Service surfaces

- FastAPI endpoints for health, rules, rule-pack import/export, version diff, governance (pins + **deprecations** with enforce), **LSP** (`/ide/lsp/analyze`), simulations (default, shadow, coverage, **counterfactual**, **chain**), time-travel **debug** capture/replay, deployment config, DQ, Workbench helper routes
- Browser **Rules Workbench** at `/workbench/`: **Monaco** DRL editor, **validate** (parse) + **LSP** diagnostics, **Overview** (stats, charts), **light/dark theme** synced with editor, assets with filters, per-version **activate/deactivate** (see API), simulation, deployment readout, template helper, **Phase 3** pack + diff, **Phase 4** governance pane
- Python package APIs for parser, compiler, executor, store, and runtime modules
- Data quality API endpoint for check evaluation and summarized violation outputs
- Optional **`SPARKRULES_API_KEY`**: also required for sensitive **GET**s on rules, deployment, and governance when set (public: `/health`, OpenAPI, `OPTIONS`, static `/workbench/-` shell)
- **Docker** `Dockerfile` and `docker compose`; **CI** can push images to **GHCR** and publish **sdist/wheel** to **PyPI** (trusted publishing) - [PUBLISHING.md](PUBLISHING.md)
- **Deploy** documentation for AWS Glue, Databricks, GCP Dataproc, and Azure Synapse (config-driven)
- **Phase 3:** rule pack, asset search, group/namespace filter, DRL version diff, API key (writes + sensitive reads)
- **Phase 4:** rule **namespace**, dev/stage/prod **promotion pins** (in-memory), **deprecation** records and **enforce** to deactivate live versions - [GOVERNANCE.md](GOVERNANCE.md); lakehouse benchmark checklist: [BENCHMARKS.md](BENCHMARKS.md#phase-4--lakehouse-benchmarks)
- Release: [PUBLISHING.md](PUBLISHING.md) (local build, **PyPI on `v*` tags** or manual, **ghcr.io** images on branch/tag push)

## Metadata lifecycle

- Versioned rule metadata lifecycle operations
- Active window overlap detection and conflict protection
- Pluggable store backends (`in_memory` production-ready; `pickle_file` for persistent local storage; DuckDB, Iceberg, and Postgres backends planned)

## Observability

- Structured logging helpers
- Metrics endpoint support
- Runtime health analysis for UI integration payloads
- Slow-stage, high-shuffle, and task-failure issue detection

## Delivery quality

- Full test suite with unit, property, and integration coverage
- **100% line coverage** gate on `src/sparkrules` (`pytest tests/unit/ --cov=src/sparkrules`, `fail_under=100` in `pyproject.toml`)
- **DRL parse caching** (LRU 256) for repeated evaluations
- Architecture scope and extension points: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)

## Regulatory compliance

- **Adverse-action reason aggregation**  -  `build_adverse_action_notice()` collects reason codes from rule chain evaluations into structured notices for ECOA/FCRA (US) and GDPR Art 22 (EU)
- Principal reasons capped at 4 per ECOA standard
- Deduplicated, priority-ordered reason codes with audit metadata

## Data profiling

- **`profile_rows()`**  -  per-field statistics over a batch of rows
- Completeness (% non-null), uniqueness (% distinct)
- Numeric: mean, stddev, min, max, p25, p50, p75
- Categorical: top-N value counts
- Structured `DataProfile` with `.to_dict()` for API/JSON output
