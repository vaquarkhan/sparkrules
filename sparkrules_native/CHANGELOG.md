# Changelog — sparkrules-native

All notable changes to this crate **(PyPI package `sparkrules-native`)** appear here.

## [Unreleased]

### Added

- **Tier-1 scalar interpreter:** `compile_rulepack`, `score_rows`, `rulepack_hash`, `native_version`.
- **`score_rows` FFI:** **`list[str]`** compact JSON facts in, **`list[str]`** JSON **`ScoreResult`** rows out (CPython **`json`**, Rust **`serde_json`**). Requires **PyO3 0.23+**.
- Stable JSON ingestion (`native_schema=1`) from `sparkrules.RulePack.to_native_json()`.

### Removed

- **`py_json`** module (PyDict↔`serde_json::Value` per row) — benchmarked slower than the JSON-string path with the current **`Value`**-based interpreter.
