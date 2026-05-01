# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Versioned metadata store with pluggable backends (in_memory, duckdb, iceberg, postgres)
- Rule governance: namespaces, dev/stage/prod promotion pins, deprecation workflow
- Optional PySpark integration via `apply_drl()` for cluster DataFrame evaluation
- Platform configuration: local, AWS Glue, Databricks, GCP Dataproc, Azure Synapse
- Python client SDK (`SreClient`) and CLI (`sparkrules-cli`)
- Rule pack export/import, version diff, asset search with filters
- Optional API key authentication for mutating and sensitive endpoints
- Docker support with Dockerfile and docker-compose
- CI/CD: GitHub Actions for tests, PyPI release (trusted publishing), Docker image push
- 521 tests with 100% line coverage gate, property-based testing with Hypothesis
- Comprehensive documentation: features, architecture, use cases, benchmarks, governance

### Changed
- **BREAKING:** Package renamed from `sre` to `sparkrules` — all imports changed
- **BREAKING:** CLI entry points renamed: `sre-cli` → `sparkrules-cli`, `sre-drl-smoke` → `sparkrules-drl-smoke`
- License changed from SparkRules Non-Commercial Citation License 1.0 to Apache License 2.0
- CI expanded: Python 3.11/3.12/3.13 matrix, ruff linting, pip-audit security scanning
- Added `py.typed` marker for PEP 561 type checking support
- Added PyPI metadata: keywords, classifiers, project URLs

[1.0.0]: https://github.com/vaquarkhan/sparkrules/releases/tag/v1.0.0
