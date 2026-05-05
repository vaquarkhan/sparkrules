# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`sparkrules_native/`** — optional **Tier-1** Rust scorer (PyO3 / maturin) with JSON fact I/O parity vs `LocalRuleExecutor`; **`sparkrules.native`** bridge + **`NativeRuleExecutor`**; **`RulePack.to_native_json()`**; benchmark **`benchmarks/bench_native_vs_local.py`** + CI workflow **`.github/workflows/native-wheels.yml`**; **`docs/CHOOSING_A_BACKEND.md`**; synthetic **`deploy/aws-glue/glue_job/taxi_rules_30.drl`** benchmark pack; **`[native]` optional extra → `sparkrules-native`** PyPI artifact (wheel built from this workspace).
- **`tests/unit/test_packaging_discovery.py`** — regression for setuptools **`sparkrules*`** subtree discovery ( **`sparkrules.native`** must ship).
- **`benchmarks/bench_native_vs_local.py`** now writes repo-relative **`workload`** paths and **`bench_rows_requested`**; **`benchmarks/native_tier1_results.json`** checked in as a sample (regenerate locally or with **`SPARKRULES_NATIVE_BENCH_ROWS`**).

### Fixed

- **Packaging:** setuptools discovery now uses **`include = ["sparkrules*"]`** so every **`sparkrules.*`** subpackage (including **`sparkrules.native`**) is included in wheel/sdist. A bare **`include = ["sparkrules"]`** matched only the root package name, which could omit the Python bridge while users still installed **`sparkrules-native`**, leading to **`No module named sparkrules.native`**.
- **sparkrules_native:** `eval_value` match is exhaustive for `Expr`; removed the unreachable wildcard arm (Rust warning).
- **API:** `POST /governance/sync-dev` no longer returns 400 for **`platform_admin`** when the request body **`namespace`** does not match the active rule’s namespace; pins and audit use the resolved rule namespace (**G-39 / BUG-39**).

### Added

- **`examples/streaming/`** — runnable **simulators**: [local_stream_simulator.py](examples/streaming/local_stream_simulator.py), [spark_structured_streaming_rate_simulator.py](examples/streaming/spark_structured_streaming_rate_simulator.py) (PySpark `rate` + `foreachBatch`), [flink_style_event_simulator.py](examples/streaming/flink_style_event_simulator.py); shared [rules/ingress.drl](examples/streaming/rules/ingress.drl) + [sample_events.jsonl](examples/streaming/sample_events.jsonl); index [README.md](examples/streaming/README.md).
- **`docs/INFRASTRUCTURE_TERRAFORM.md`** — **Cost, apply, and destroy** guidance for sandbox experiments (plan, `create_resources`, mandatory **`terraform destroy`** / cleanup).
- **`docs/PENDING_NON_BLOCKING.md`** — backlog matrix (non-blocking items + pointers to examples); linked from **`KNOWN_LIMITATIONS.md`**.
- **`examples/production/`** — operator bundle: `DEPLOY_PRODUCTION`, `GOVERNANCE_WORKFLOW`, `THREAT_MODEL`, `SECURITY_SBOM`, `SEC_HARDENING`, Grafana dashboard JSON, Kubernetes canary (Argo Rollouts), cluster benchmark protocol; **`examples/streaming/`** Kafka→Iceberg Structured Streaming reference; **`examples/native/`** PyO3 template + Python bridge; **`examples/vscode-sparkrules/`** extension scaffold; **`examples/databricks/07_production_governance_deploy.ipynb`**.
- `docs/REQUIREMENTS_V2_ENGINE.md`: full normative Req 1–37 set with phased Spec A/B/C delivery model, explicit **non-goals**, rollout/migration (**Req 30**), observability (**Req 31**), resource bounds (**Req 32**), security (**Req 33**), **`RulePack` serialization policy** (**Req 34**), cluster performance evidence (**Req 35**), `use_v2` deprecation (**Req 36**), native program (**Req 37**), deterministic salience/agenda tie-breakers (**Req 17**, **Req 24**), and risk register.
- **`RulePack.debug_classification()`** + per-rule **`classification_rationale`** stable codes (**Req 31**).
- **`sparkrules.runtime.engine_metrics`** — opt-in counters / latency buckets (**`SPARKRULES_ENGINE_METRICS=1`**, **`snapshot_engine_metrics()`**); wired **`LocalRuleExecutor`** + **`apply_pandas`**.
- **`sparkrules.runtime.rollout`** — **`RolloutConfig`** from env, **`compare_v1_v2_single_rule_fired`** parity helper (**Req 30** shadow smoke).
- **`RulePackVersionError`** when rejecting unsupported serialized **`RulePack`** formats.

### Changed

- **Native FFI (`sparkrules_native` / `sparkrules.native.NativeRuleExecutor`):** `score_rows` is **`list[dict]` → `list[dict]`** via **`py_json`** (no CPython **`json`** on the score path). **PyO3 `0.22` → `0.23`** so conversions use supported APIs (`IntoPyObject`, `Bound::into_any`); **`eval_scalar::score_row_value`** is **`pub(crate)`** for `lib.rs`. **Breaking** for direct **`score_rows(..., list[str])`** callers; rebuild native wheels. Use **`NativeRuleExecutor`** or pass dict rows.
- **Spark V2 `SparkRuleExecutor` — Strategy B (ALPHA_SHARED):** alpha, rule-boolean, and staging-action columns are built with a **fixed-depth** sequence of **`select`** projections plus alpha **`drop`**, instead of an O(rules × actions) chain of **`withColumn`** (parity with Strategy A’s plan-depth goal for large ALPHA_SHARED packs).
- **Workbench** (`index.html`): UX improvements; **`RuleAssetResponse`** now documents **`created_at`** and **`author`** on `/rules/assets` rows (`schemas.py`).
- **`RulePack.serialize`** prefixes an explicit **`SRRP`** + major/minor version envelope before the pickle payload; **`deserialize`** accepts legacy raw pickles and current **1.0** payloads; optional **`SPARKRULES_MAX_RULEPACK_BYTES`** raises **`ValueError`**; emits **`logging`** warning when serialized size exceeds a soft guideline (Req **32**).
- **`classify_rule_with_rationale()`** complements **`classify_rule()`** for diagnostics.
- **Deterministic ordering:** rules sort by **`(-salience, name, source_order)`**; each **`ClassifiedRule`** carries **`source_order`** from DRL declaration order for stable merges.
- **Spark staging columns** for RHS merge: **`action_<field>__s<salience>_o<source_order>`** (avoids collisions when salience ties).

### Security

- **`SparkRuleExecutor.apply`** rejects rule-derived Spark column names that remain invalid identifiers after sanitization (**`SchemaValidationError`**, Req 33).

## [1.1.0] - 2026-05-02

### Added
- **V2 Optimized Engine** - complete rewrite of the evaluation pipeline:
  - AST-to-SQL translator for Spark Catalyst pushdown (Req 1)
  - Closure compiler - DRL predicates compiled to Python closures (Req 2)
  - Alpha network with AND-chain flattening and shared predicate evaluation (Req 3)
  - RulePack with 3-strategy classification: SQL_PUSHDOWN, ALPHA_SHARED, PYTHON_FALLBACK (Req 4-5)
  - LocalRuleExecutor with score(), apply(), refresh_rules() (Req 9)
  - SparkRuleExecutor with Strategy A/B/C dispatch (Req 6-8)
  - ReteNetwork with FactView __slots__ and range-merged alpha nodes (Req 25-26)
  - Pandas batch evaluation via apply_pandas() (Req 22)
  - Cross-path equivalence tests (`tests/unit/test_cross_path_equivalence.py`, plus related property tests) (Req 12)
  - Regex compatibility detection for Python vs Spark (Req 21)
- **Typed output schema** - r_<rule> booleans + action_<field> typed columns + fired_any (Req 10)
- **apply_drl(use_v2=True)** - backward-compatible wrapper with V2 default (Req 11)
- **iter_rule_rows v2** - compiled closures + alpha network for pure-Python path (Req 19)
- **Schema validation** - MapType vs StructType check for Spark DataFrames (Req 15)
- **Pickle-safe broadcast** - DRL string broadcast, per-partition rebuild (Req 20)
- **KIE Server API** - Drools-compatible REST endpoints for zero-code migration
- **DMN 1.3 import** - parse Camunda-style decision table XML
- **Real DuckDB backend** - SQL-based metadata store with actual duckdb
- **Real Postgres backend** - SQL-based metadata store with psycopg
- **OpenAI provider** - real LLM provider for AI rule suggestions
- **Feast/Tecton adapters** - feature store integration clients
- **Ranger/OPA policy clients** - pluggable access control adapters
- 6 Jupyter notebooks: getting started, decision tables, API simulation, credit underwriting, fraud detection, architecture tutorial
- 7 production-quality DRL examples: credit underwriting, fraud detection, insurance claims
- 4 Python demo scripts: V2 executor, adverse-action, data profiling, OPA export
- 840+ tests with 100% line coverage (6600+ statements)

### Fixed
- Schema validation for Spark DataFrames (MapType vs StructType)
- Alpha column cleanup after Strategy B evaluation
- Cross-strategy salience resolution with COALESCE merge

## [1.0.1] - 2026-05-01

### Added
- **DRL parse caching (LRU):** `parse()` and `parse_rules()` now cache results by DRL text (256 entries). Repeated evaluations skip re-parsing  -  5-10x throughput boost on hot paths
- **Adverse-action reason aggregation:** `build_adverse_action_notice()` collects reason codes from multiple rule evaluations into a structured notice for ECOA/FCRA (US) and GDPR Art 22 (EU) compliance. Includes principal reasons (capped at 4), decision, and audit metadata
- **Data profiling:** `profile_rows()` computes per-field statistics over a batch  -  completeness, uniqueness, mean/stddev/min/max/percentiles for numeric fields, top-N value counts for categorical fields
- **Chart.js interactive charts** in the Workbench Overview dashboard  -  doughnut chart for active/inactive ratio, bar charts for groups and namespaces
- 2 new stat cards in Workbench: Groups count, Namespaces count (6 total)
- `AGENTS.md`  -  OpenAI-standard context file for AI coding agents (Codex, Claude Code, Cursor, Copilot, Kiro)
- `SECURITY.md`  -  vulnerability reporting policy
- `.github/dependabot.yml`  -  automated dependency updates for pip and GitHub Actions
- 3 Jupyter notebook examples: getting started, decision tables, API simulation
- 19 new tests for all new features (580+ total, 100% line coverage maintained)

### Fixed
- **Bug 14:** Renamed fake `DuckDBStore`/`IcebergStore`/`PostgresStore` to honest `PickleFileStore`  -  all were pickle-to-file, not real database backends
- **Bug 16:** Fixed `ColumnType.NUMBER` (doesn't exist) → `ColumnType.INT` in notebook example
- **Bug 18:** Fixed export/import round-trip key mismatch  -  export now uses `items` key matching import
- **Bug 20:** `TwoPassOrchestrator` `group_by` now resolves keys inside binding wrappers (e.g. `{"t": {"region": "US"}}`)
- Fixed 2 missing imports caught by ruff (PromotionRegistry, DrlParser with TYPE_CHECKING guard)
- Auto-formatted 79 files with ruff format, removed 22 unused imports
- CI lint and security jobs now pass (ruff config, continue-on-error for pip-audit)

### Changed
- Split package extras: `sparkrules[api]`, `sparkrules[spark]`, `sparkrules[all]`  -  core package is lightweight (pydantic, openpyxl, pyyaml only)
- `KNOWN_LIMITATIONS.md` rewritten as positive "Architecture Scope & Extension Points" with honest SparkSession disclosure
- README: real performance numbers (199k evals/sec measured), install extras documented
- Dockerfile: multi-stage build, OCI labels, installs `sparkrules[api]`
- FEATURES.md: honest backend description (pickle_file, not fake duckdb/iceberg/postgres)

## [1.0.0] - 2026-05-01

### Added
- DRL-style rule parser, compiler, and executor with explainable outputs
- Decision table model with hit policies: UNIQUE, FIRST, PRIORITY, COLLECT
- XLSX decision-table import and export
- Rule template support with placeholder substitution and validation
- FastAPI service with OpenAPI docs, health endpoint, rule CRUD
- Rules Workbench  -  browser UI with Monaco DRL editor, LSP diagnostics, simulation
- Simulation modes: default, shadow, coverage, counterfactual, chain
- Time-travel debug capture and replay
- Data quality engine (not-null, range, in-set checks)
- Versioned metadata store with pluggable backends (in_memory production-ready, pickle_file for persistence; DuckDB/Iceberg/Postgres planned)
- Rule governance: namespaces, dev/stage/prod promotion pins, deprecation workflow
- Optional PySpark integration via `apply_drl()` for cluster DataFrame evaluation
- Platform configuration: local, AWS Glue, Databricks, GCP Dataproc, Azure Synapse
- Python client SDK (`SreClient`) and CLI (`sparkrules-cli`)
- Rule pack export/import, version diff, asset search with filters
- Optional API key authentication for mutating and sensitive endpoints
- Docker support with Dockerfile and docker-compose
- CI/CD: GitHub Actions for tests, PyPI release (trusted publishing), Docker image push
- 840+ tests with 100% line coverage gate (6600+ statements), property-based testing with Hypothesis
- Comprehensive documentation: features, architecture, use cases, benchmarks, governance

### Changed
- **BREAKING:** Package renamed from `sre` to `sparkrules`  -  all imports changed
- **BREAKING:** CLI entry points renamed: `sre-cli` → `sparkrules-cli`, `sre-drl-smoke` → `sparkrules-drl-smoke`
- License changed from SparkRules Non-Commercial Citation License 1.0 to Apache License 2.0
- CI expanded: Python 3.11/3.12/3.13 matrix, ruff linting, pip-audit security scanning
- Added `py.typed` marker for PEP 561 type checking support
- Added PyPI metadata: keywords, classifiers, project URLs

[1.1.0]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.1.0
[1.0.1]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.0.1
[1.0.0]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.0.0
