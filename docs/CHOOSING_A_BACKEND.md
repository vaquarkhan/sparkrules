# Choosing a backend

| Scenario | Recommended | Notes |
|----------|-------------|--------|
| **Single-row / embedded / tests** | `LocalRuleExecutor` | Default Python V2 (`AlphaNetwork` + closures). Always available. Reference for parity. |
| **Throughput on one machine (Tier-1 Rust)** | `NativeRuleExecutor` + `sparkrules-native` wheel | Optional install. Same `score` / `apply` parity contract as local. Parses rules from JSON produced by Python (`RulePack.to_native_json`). |
| **DataFrame / notebooks** | `apply_pandas` / batch helpers | Keeps classification + vectorized paths documented elsewhere. |
| **Cluster-scale tabular scoring** | `SparkRuleExecutor` / `apply_drl` | Spark **WholeStageCodegen** already wins over a JVM ↔ Rust FFI per row — do **not** route Spark through native (see roadmap). |

**Fallback:** omit the wheel (`pip install sparkrules` only) — everything behaves as today. **`SPARKRULES_NATIVE_DISABLE=1`** skips loading native even when installed.

**When Tier-2 Arrow batch scoring ships**, widen this table with batch APIs and parquet-friendly paths.
