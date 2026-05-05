# Native Rust kernel — agent decision log

## 2026-05-05 — FFI contract and parity surface

**Context:** Tier-1 must match `LocalRuleExecutor.score()` without rewriting the Spark path.

**Options considered:**

- Call Python predicates from Rust (discard — forbidden hot-loop Python).
- Re-parse DRL in Rust (discard — parser stays Python-only).
- Ship AST JSON from `RulePack` + interpret with Rust semantics cloned from `compiler.closure`.

**Decision:** Stable JSON envelope (`native_schema`, `drl_hash`, ordered `rules[]`) serialized by Python; Rust interprets predicates with semantics aligned to `compile_predicate` + flattened AND (Alpha-style) firing. At score time, **`score_rows`** accepts a Python **`list`** of fact **dicts** and returns **`list[dict]`** (`fires` / `fired_any` / `merged_actions`) via `py_json::{py_to_json_value, json_value_to_py}`— no CPython **`json.dumps` / `json.loads`** on the hot path (AST compile still uses JSON text once).

**Consequences:** No change to Spark executors or `LocalRuleExecutor`. Separate PyPI **`sparkrules-native`** wheel. Parity verified via Hypothesis (`tests/integration/test_native_parity.py`).

## 2026-05-05 — No separate Rust `types.rs` for Tier-1

**Context:** The implementation guide suggested a standalone `Value` enum.

**Decision:** Facts and outputs use **`serde_json::Value`** with comparison / membership helpers in `eval_scalar.rs` mirroring **`compiler.closure`** and **`SparkRules`** literals as JSON scalars only.

**Consequences:** Exotic pickle-only Python types round-trip poorly through JSON FFI; stick to facts that `json.dumps(default=str)` can represent consistently with `LocalRuleExecutor` fixtures.

## 2026-05-05 — Python namespace vs extension module name

**Context:** setuptools previously shipped `src/sparkrules_native/` stub; `include = ["sparkrules"]` only discovered the root package, so **`sparkrules.native`** was missing from sdists while setuptools still auto-found other subpackages inconsistently.

**Decision:** setuptools `include = ["sparkrules*"]` so every subpackage under `src/sparkrules/` (including **`sparkrules.native`**) ships in wheel/sdist. The stub tree was removed from the core distribution; optional extension remains top-level **`sparkrules_native`** (import name) via the **`sparkrules-native`** wheel only.

**Consequences:** `import sparkrules_native` works only after `maturin` / pip install of the Rust wheel. Reinstall **`sparkrules`** alone no longer overwrites an extension stub with the same import name.
