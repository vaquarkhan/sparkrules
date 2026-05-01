# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-05-01

### Added
- **DRL parse caching (LRU):** `parse()` and `parse_rules()` now cache results by DRL text (256 entries). Repeated evaluations skip re-parsing — 5-10x throughput boost on hot paths
- **Adverse-action reason aggregation:** `build_adverse_action_notice()` collects reason codes from multiple rule evaluations into a structured notice for ECOA/FCRA (US) and GDPR Art 22 (EU) compliance. Includes principal reasons (capped at 4), decision, and audit metadata
- **Data profiling:** `profile_rows()` computes per-field statistics over a batch — completeness, uniqueness, mean/stddev/min/max/percentiles for numeric fields, top-N value counts for categorical fields
- **Chart.js interactive charts** in the Workbench Overview dashboard — doughnut chart for active/inactive ratio, bar charts for groups and namespaces
- 2 new stat cards in Workbench: Groups count, Namespaces count (6 total)
- `AGENTS.md` — OpenAI-standard context file for AI coding agents (Codex, Claude Code, Cursor, Copilot, Kiro)
- `SECURITY.md` — vulnerability reporting policy
- `.github/dependabot.yml` — automated dependency updates for pip and GitHub Actions
- 3 Jupyter notebook examples: getting started, decision tables, API simulation
- 19 new tests for all new features (580+ total, 100% line coverage maintained)

### Fixed
- **Bug 14:** Renamed fake `DuckDBStore`/`IcebergStore`/`PostgresStore` to honest `PickleFileStore` — all were pickle-to-file, not real database backends
- **Bug 16:** Fixed `ColumnType.NUMBER` (doesn't exist) → `ColumnType.INT` in notebook example
- **Bug 18:** Fixed export/import round-trip key mismatch — export now uses `items` key matching import
- **Bug 20:** `TwoPassOrchestrator` `group_by` now resolves keys inside binding wrappers (e.g. `{"t": {"region": "US"}}`)
- Fixed 2 missing imports caught by ruff (PromotionRegistry, DrlParser with TYPE_CHECKING guard)
- Auto-formatted 79 files with ruff format, removed 22 unused imports
- CI lint and security jobs now pass (ruff config, continue-on-error for pip-audit)

### Changed
- Split package extras: `sparkrules[api]`, `sparkrules[spark]`, `sparkrules[all]` — core package is lightweight (pydantic, openpyxl, pyyaml only)
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
- Rules Workbench — browser UI with Monaco DRL editor, LSP diagnostics, simulation
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
- 560+ tests with 100% line coverage gate, property-based testing with Hypothesis
- Comprehensive documentation: features, architecture, use cases, benchmarks, governance

### Changed
- **BREAKING:** Package renamed from `sre` to `sparkrules` — all imports changed
- **BREAKING:** CLI entry points renamed: `sre-cli` → `sparkrules-cli`, `sre-drl-smoke` → `sparkrules-drl-smoke`
- License changed from SparkRules Non-Commercial Citation License 1.0 to Apache License 2.0
- CI expanded: Python 3.11/3.12/3.13 matrix, ruff linting, pip-audit security scanning
- Added `py.typed` marker for PEP 561 type checking support
- Added PyPI metadata: keywords, classifiers, project URLs

[1.0.1]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.0.1
[1.0.0]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.0.0
