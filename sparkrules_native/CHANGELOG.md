# Changelog — sparkrules-native

All notable changes to this crate **(PyPI package `sparkrules-native`)** appear here.

## [Unreleased]

### Added

- **Tier-1 scalar interpreter:** `compile_rulepack`, `score_rows`, `rulepack_hash`, `native_version`.
- **`score_rows` FFI:** facts are a Python `list` of row dicts; return value is a list of result dicts (no JSON strings across the boundary; see `py_json` module).
- Stable JSON ingestion (`native_schema=1`) from `sparkrules.RulePack.to_native_json()`.
