# Native Rust kernel — agent decision log

## 2026-05-05 — FFI contract and parity surface

**Context:** Tier-1 must match `LocalRuleExecutor.score()` without rewriting the Spark path.

**Options considered:**

- Call Python predicates from Rust (discard — forbidden hot-loop Python).
- Re-parse DRL in Rust (discard — parser stays Python-only).
- Ship AST JSON from `RulePack` + interpret with Rust semantics cloned from `compiler.closure`.

**Decision:** Stable JSON envelope (`native_schema`, `drl_hash`, ordered `rules[]`) serialized by Python; Rust interprets predicates with semantics aligned to `compile_predicate` + flattened AND (Alpha-style) firing. PyO3 returns **JSON strings** per row so Python constructs `ScoreResult` / `RuleFire` unchanged.

**Consequences:** No change to Spark executors or `LocalRuleExecutor`. Separate PyPI **`sparkrules-native`** wheel. Parity verified via Hypothesis (`tests/integration/test_native_parity.py`).

## 2026-05-05 — No separate Rust `types.rs` for Tier-1

**Context:** The implementation guide suggested a standalone `Value` enum.

**Decision:** Facts and outputs use **`serde_json::Value`** with comparison / membership helpers in `eval_scalar.rs` mirroring **`compiler.closure`** and **`SparkRules`** literals as JSON scalars only.

**Consequences:** Exotic pickle-only Python types round-trip poorly through JSON FFI; stick to facts that `json.dumps(default=str)` can represent consistently with `LocalRuleExecutor` fixtures.

## 2026-05-05 — Python namespace vs extension module name

**Context:** setuptools previously shipped `src/sparkrules_native/` stub.

**Decision:** setuptools `include = ["sparkrules"]` only; optional extension remains top-level **`sparkrules_native`** (import name). Supported API lives under **`sparkrules.native`** (bridge + executor).

**Consequences:** `import sparkrules_native` works only after `maturin` / pip install of the Rust wheel.
