# Features

For production scope, unsupported DRL/Spark edges, and execution caveats, see **[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)**.

## Core engine

- DRL-style rule parsing and evaluation
- Salience-based priority control
- Agenda group and activation group execution controls
- Explainable outputs with bound data and reason codes
- Optional `SQL_JOIN` / multi-pattern path for list-valued fact bindings

## V2 optimized engine (new)

- **AST-to-SQL translator** - DRL predicates translated to Spark SQL for Catalyst pushdown
- **Closure compiler** - predicates compiled to Python closures at parse time (5-10x faster)
- **Alpha network** - shared predicate evaluation across rules (Rete-style deduplication)
- **RulePack** - structured, salience-ordered, classified rule collection
- **Three execution strategies**: SQL_PUSHDOWN, ALPHA_SHARED, PYTHON_FALLBACK
- **LocalRuleExecutor** - Python-native scoring with compiled closures + alpha network
- **NativeRuleExecutor** (optional **`sparkrules-native`** wheel — build/CI artifact; **not on PyPI** yet / `[native]` extra empty until publish) — Rust Tier-1 scalar scorer, JSON fact I/O, parity with `LocalRuleExecutor.score()`; see [NATIVE_TIER1.md](NATIVE_TIER1.md)
- **SparkRuleExecutor** - three-strategy Spark dispatch with typed output columns (Spark ``RLIKE`` vs Python ``re``: see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md))
- **ReteNetwork** - FactView with `__slots__`, range-merged alpha nodes, frozenset membership
- **Pandas batch evaluation** - `apply_pandas()` for vectorized evaluation without Spark
- **Cross-path equivalence** - unit + property coverage in `tests/unit/test_cross_path_equivalence.py` and selected `tests/property/` cases
- **DRL parse caching** (LRU 256) for repeated evaluations

## Regulatory compliance (new)

- **Adverse-action notices** - `build_adverse_action_notice()` for ECOA/FCRA/GDPR Art 22
- Principal reasons capped at 4 per ECOA standard
- Deduplicated, priority-ordered reason codes with audit metadata

## Data quality and profiling (new)

- **Statistical profiling** - `profile_rows()` for completeness, uniqueness, mean/stddev/percentiles
- DQ checks: not-null, range, in-set, regex, uniqueness, freshness, column sum, row count, table counts
- Severity levels: INFO, WARN, ERROR, CRITICAL with tolerance thresholds

## Policy export (new)

- **OPA/Rego export** - `export_to_rego()` converts DRL to Open Policy Agent format
- **DMN 1.3 import** - parse Camunda-style decision table XML

## Authoring formats

- DRL text
- Decision table JSON model
- XLSX decision table import/export
- Template-driven guided field schema generation for UI/editor surfaces

## Execution and runtime

- Single-fact and batch-style execution paths
- Spark dataframe helper paths for partition processing - **optional**; default API path is pure Python ([SPARK_INTEGRATION.md](SPARK_INTEGRATION.md))
- Replay metadata model for deterministic re-runs
- Spark version targeting for Spark 3.x / 4.x runtimes with normalization (`3`, `3.5`, `4`, `4.2`, …); **default target `4.0`** in `EngineConfig`
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
- Optional **browser login** for Workbench (`SPARKRULES_WORKBENCH_AUTH`) — **the shipped static shell hides the sign-in form by default** (`WORKBENCH_LOGIN_UI_ENABLED = false`); use **`SPARKRULES_API_KEY`** or leave workbench auth unset for typical dev ([WORKBENCH_LOGIN.md](WORKBENCH_LOGIN.md))
- **Infrastructure as code (Terraform)** — reusable **AWS modules** (`s3-artifacts-aws`, `emr-ec2-roles-aws`), roots for **EMR / Glue / EKS / Databricks / GCP / Azure**, **`terraform.tfvars.example`** per root, and a production **deployment runbook** — [INFRASTRUCTURE_TERRAFORM.md](INFRASTRUCTURE_TERRAFORM.md), [examples/infrastructure/](../examples/infrastructure/)
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
- Pluggable store backends: `in_memory`; **DuckDB** and **Postgres** SQL metadata stores; **Iceberg**-hydrating store with optional **pyiceberg** append sink or pickle-on-disk fallback when no sink is configured (`create_rule_store` in `sparkrules.store.backends`)

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

- **Adverse-action reason aggregation**  -  `build_adverse_action_notice()`, `adverse_action_record()`, and `adverse_action_counterfactual_summary()` (base vs hypothetical context) for ECOA/FCRA (US) and GDPR Art 22 (EU) counsel-reviewable templates
- Principal reasons capped at 4 per ECOA standard
- Deduplicated, priority-ordered reason codes with audit metadata

## Data profiling

- **`profile_rows()`**  -  per-field statistics over a batch of rows
- Completeness (% non-null), uniqueness (% distinct)
- Numeric: mean, stddev, min, max, p25, p50, p75
- Categorical: top-N value counts
- Structured `DataProfile` with `.to_dict()` for API/JSON output
