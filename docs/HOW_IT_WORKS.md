# How SparkRules works

## High-level flow

1. Author rules in DRL or decision-table form.
2. Parse and validate rule syntax and references.
3. Compile rules into execution-ready structures.
4. Evaluate facts and produce rule results.
5. Persist and/or emit run metadata and result data.
6. Replay by reusing pinned run context and rule versions.

## Main components

- **Parser**: converts DRL text into AST structures.
- **Compiler**: prepares rule packages and strategy metadata.
- **Executor**: evaluates compiled logic against facts.
- **Metadata store**: versions rules and resolves active sets.
- **Runtime helpers**: replay, cache, streaming support primitives.
- **API layer**: exposes operational endpoints; Workbench (static), **LSP** analyze, **simulations** (including counterfactual and **chain**), time-travel **debug** rows, and governance (pins + **deprecations**).

## Execution controls

- Salience: prioritizes competing activations.
- Agenda groups: scope which rules run in a stage.
- Activation groups: XOR behavior for competing rules.

## Observability, rollout, and limits (V2)

- **Classification transparency:** `RulePack.debug_classification()` returns each rule’s strategy plus a stable **`classification_rationale`** code (e.g. `SQL_PUSH_TRANSLATABLE`, `PYTHON_ONLY_REGEX`).
- **Counters (opt-in):** set **`SPARKRULES_ENGINE_METRICS=1`** then poll **`snapshot_engine_metrics()`** from `sparkrules.runtime.engine_metrics` (evaluations, row counts, firings-by-strategy, translation-failure tally, coarse latency buckets). **`LocalRuleExecutor`** and **`apply_pandas`** record automatically when metrics are enabled.
- **Structured logs:** at **INFO**, `LocalRuleExecutor` emits one line per firing with rule name, strategy, salience, and reason codes.
- **Rollout knobs:** **`rollout_config_from_environ()`** reads **`SPARKRULES_SHADOW_DUAL_EVAL`**, **`SPARKRULES_ENGINE_METRICS`**, **`SPARKRULES_MAX_RULEPACK_BYTES`**. For single-rule parity smoke tests use **`compare_v1_v2_single_rule_fired(fact, drl)`**.
- **Serialized RulePack caps:** optional hard limit via **`SPARKRULES_MAX_RULEPACK_BYTES`**; soft warning still applies when blobs exceed **`RULEPACK_LARGE_SERIALIZE_WARN_BYTES`**.

See **docs/REQUIREMENTS_V2_ENGINE.md** (Req **30–34**) for normative wording.

## Data and output model

- Rule evaluation returns fired state, bound field values, and action outputs.
- Runtime records include run identifiers and reproducibility metadata.
- Store and runtime APIs are designed for deterministic behavior under replay.
