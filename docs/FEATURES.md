# Features

## Core engine

- DRL-style rule parsing and evaluation
- Salience-based priority control
- Agenda group and activation group execution controls
- Explainable outputs with bound data and reason codes
- Optional SQL-join execution path flag in executor for multi-pattern rules

## Authoring formats

- DRL text
- Decision table JSON model
- XLSX decision table import/export
- Template-driven guided field schema generation for UI/editor surfaces

## Execution and runtime

- Single-fact and batch-style execution paths
- Spark dataframe helper paths for partition processing
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

- FastAPI endpoints for health, rules, and simulation
- Browser **Rules Workbench** at `/workbench/` (assets, DRL validate, simulation, deployment readout, template helper)
- Python package APIs for parser, compiler, executor, store, and runtime modules
- Data quality API endpoint for check evaluation and summarized violation outputs
- Reference **Docker** image build and `docker compose` for local full-stack runs
- **Deploy** documentation for AWS Glue, Databricks, GCP Dataproc, and Azure Synapse (config-driven)
- **Phase 3:** rule pack import/export, asset search, group filter, DRL version diff API and workbench panes; optional `SPARKRULES_API_KEY` gate for `POST`/`PUT`/`PATCH`/`DELETE`
- **Phase 4:** rule **namespace**, dev/stage/prod **promotion pins** (in-memory) with sync and adjacent promote on the API and Workbench — see [GOVERNANCE.md](GOVERNANCE.md); lakehouse benchmark checklist in [BENCHMARKS.md](BENCHMARKS.md#phase-4--lakehouse-benchmarks)
- Release/publish notes: [PUBLISHING.md](PUBLISHING.md) (local build, CI artifacts, org-specific PyPI and container registry)

## Metadata lifecycle

- Versioned rule metadata lifecycle operations
- Active window overlap detection and conflict protection
- Pluggable store backends (`in_memory`, `duckdb`, `iceberg`, `postgres`)

## Observability

- Structured logging helpers
- Metrics endpoint support
- Runtime health analysis for UI integration payloads
- Slow-stage, high-shuffle, and task-failure issue detection

## Delivery quality

- Full test suite with unit, property, and integration coverage
- 100% line coverage gate on `src/sre`
