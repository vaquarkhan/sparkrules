# Examples

## Quick start

```bash
pip install sparkrules[api]
```

## DRL rule files

| File | Domain | Features demonstrated |
|------|--------|---------------------|
| [drl/minimal.drl](drl/minimal.drl) | Basic | Simplest possible rule |
| [drl/discount_tier.drl](drl/discount_tier.drl) | Retail | Salience, AND conditions |
| [drl/credit_underwriting.drl](drl/credit_underwriting.drl) | Lending | Activation groups, reason codes, multi-rule pack |
| [drl/fraud_detection.drl](drl/fraud_detection.drl) | Payments | stop_on_fire, risk scoring, velocity checks |
| [drl/insurance_claims.drl](drl/insurance_claims.drl) | Insurance | Agenda groups, staged evaluation, claim routing |

Sample rows for the smallest DRLs live next to them — see **[drl/README.md](drl/README.md)** (`minimal_facts.json`, `discount_tier_facts.json`).

## Python scripts

| Script | What it demonstrates |
|--------|---------------------|
| [python/evaluate_drl_file.py](python/evaluate_drl_file.py) | Load and evaluate a DRL file |
| [python/api_inprocess.py](python/api_inprocess.py) | In-process FastAPI app inspection |
| [python/v2_local_executor.py](python/v2_local_executor.py) | **V2 engine**: RulePack classification, alpha network, performance benchmarks |
| [python/apply_pandas_demo.py](python/apply_pandas_demo.py) | **V2 pandas**: `apply_pandas()` vectorized / closure batch path |
| [python/refresh_rules_hot_swap.py](python/refresh_rules_hot_swap.py) | **Hot-swap**: `LocalRuleExecutor.refresh_rules()` without restart |
| [python/benchmark_v2_local_throughput.py](python/benchmark_v2_local_throughput.py) | Quick local throughput sanity check (see `docs/BENCHMARKS.md` for methodology) |
| [python/adverse_action_demo.py](python/adverse_action_demo.py) | **Regulatory**: ECOA/FCRA adverse-action notice generation |
| [python/adverse_action_counterfactual_demo.py](python/adverse_action_counterfactual_demo.py) | **Regulatory**: Compare two ``AdverseActionContext`` snapshots (added/removed reason codes) |
| [python/dmn_xml_minimal_demo.py](python/dmn_xml_minimal_demo.py) | **DMN**: Parse minimal Camunda DMN XML and evaluate a ``FIRST`` table |
| [python/graph_enricher_demo.py](python/graph_enricher_demo.py) | **Graph**: Merge in-memory graph features into a fact (``GraphEnricher``) |
| [python/dq_extended_checks_demo.py](python/dq_extended_checks_demo.py) | **DQ**: Table-scoped checks (unique, regex, sum, row count) |
| [python/data_profiling_demo.py](python/data_profiling_demo.py) | **DQ**: Statistical profiling + quality checks before rule evaluation |
| [python/opa_export_demo.py](python/opa_export_demo.py) | **Policy**: Export DRL rules to OPA Rego format |
| [python/ai_rule_suggestion_workflow_demo.py](python/ai_rule_suggestion_workflow_demo.py) | **AI**: Stub provider suggestions, simulator evidence, approval (`AiService`) |
| [python/chaos_and_perf_harness_demo.py](python/chaos_and_perf_harness_demo.py) | **Reliability / perf**: `run_chaos_scenario`, `run_perf_harness`, `scale_evidence` |
| [python/governance_promotion_pins_demo.py](python/governance_promotion_pins_demo.py) | **Governance**: `PromotionRegistry` dev→stage→prod pins + `sync_dev_from_active` |
| [python/kie_rest_migration_recipe_demo.py](python/kie_rest_migration_recipe_demo.py) | **KIE REST shim**: deploy container + stateless batch (`pip install sparkrules[api]`) |
| [python/lsp_analyze_drl_demo.py](python/lsp_analyze_drl_demo.py) | **IDE / LSP**: `analyze_drl_for_lsp` diagnostics + completions (no language-server process) |
| [python/policy_opa_ranger_demo.py](python/policy_opa_ranger_demo.py) | **Policy runtime**: OPA `query_opa` (optional live URL) + `ranger_allow_stub` |
| [python/streaming_config_and_orchestrator_demo.py](python/streaming_config_and_orchestrator_demo.py) | **Streaming contracts**: Kafka/Kinesis `FactSourceSpec` + `EngineConfig` + `StreamingOrchestrator` |
| [python/time_travel_debug_api_demo.py](python/time_travel_debug_api_demo.py) | **Debug replay**: `/debug/time-travel/capture` + `/replay` (`pip install sparkrules[api]`) |
| [python/two_pass_orchestrator_demo.py](python/two_pass_orchestrator_demo.py) | **Two-pass**: `TwoPassOrchestrator` with `group_by` aggregates + per-group quota |
| [python/udf_registry_demo.py](python/udf_registry_demo.py) | **UDF registry**: versioned `UserDefinedFunctionRegistry` + `eval_registered_pure_udf` |

## Decision tables

| File | Format |
|------|--------|
| [decision_table/first_match.json](decision_table/first_match.json) | JSON decision table with FIRST hit policy |
| [decision_table/xlsx_roundtrip_demo.py](decision_table/xlsx_roundtrip_demo.py) | XLSX export + import round-trip (`ioxls`) |

## Jupyter notebooks

| Notebook | Topic |
|----------|-------|
| [notebooks/01_getting_started.ipynb](notebooks/01_getting_started.ipynb) | DRL rules, evaluation, explainable results |
| [notebooks/02_decision_tables.ipynb](notebooks/02_decision_tables.ipynb) | Decision tables, hit policies, JSON export |
| [notebooks/03_api_simulation.ipynb](notebooks/03_api_simulation.ipynb) | REST API: validate, simulate, counterfactual |

## Spark examples

| Script | What it demonstrates |
|--------|---------------------|
| [spark/apply_drl_local.py](spark/apply_drl_local.py) | **V2** `SparkRuleExecutor.apply(df)` — typed columns, classifier printout, optional `--explain` (Catalyst) |
| [spark/apply_drl_v2_lakehouse_sink.py](spark/apply_drl_v2_lakehouse_sink.py) | **V2 + sinks**: score with `SparkRuleExecutor`, write each `create_result_sink` format (JSON snapshots; swap for real Iceberg/Delta tables in prod) |
| [spark/iter_rule_rows_no_jvm.py](spark/iter_rule_rows_no_jvm.py) | Pure-Python row iterator (no JVM needed) |

## Rule store (DuckDB / Postgres)

| Script | What it demonstrates |
|--------|---------------------|
| [store/duckdb_quickstart.py](store/duckdb_quickstart.py) | File-backed metadata with `create_rule_store("duckdb", ...)` |
| [store/postgres_quickstart.py](store/postgres_quickstart.py) | Postgres URL via `DATABASE_URL` / `--dsn` |

## End-to-end use cases

Complete domain examples with DRL rules, sample CSV data, validation scripts, and Spark jobs. Each use case includes `spark_e2e.py` calling `apply_drl(..., use_v2=True)` with `Row`/struct facts (typed V2 columns: `r_*`, `action_*`, `fired_any`).

| Use case | Domain | Files |
|----------|--------|-------|
| [usecases/lending_portfolio/](usecases/lending_portfolio/) | Lending | 50-rule underwriting pack, 90-row sample |
| [usecases/clinical_research/](usecases/clinical_research/) | Healthcare | Trial eligibility screening |
| [usecases/credit_card/](usecases/credit_card/) | Payments | Card authorization rules |
| [usecases/point_of_sale/](usecases/point_of_sale/) | Retail | POS checkout rules |
| [usecases/reward_loyalty/](usecases/reward_loyalty/) | Loyalty | Reward tier assignment |

## Feature coverage (ships in the library)

These rows map **previously undocumented gaps** to runnable scripts in this folder (no separate guide file). “Full stack” items (Kafka consumer, Databricks catalog ACLs, real Iceberg commits) remain operator-owned; the examples show the **APIs and contracts** SparkRules exposes.

| Topic | Example | What you get vs production |
|-------|---------|---------------------------|
| Spark DataFrame V2 typed columns | `usecases/*/spark_e2e.py`, `spark/apply_drl_local.py`, `spark/apply_drl_v2_lakehouse_sink.py` | Same Catalyst/V2 path as clusters; local `local[*]` master. |
| Lakehouse result sinks | `spark/apply_drl_v2_lakehouse_sink.py` | Writes JSON snapshots via `create_result_sink` labels (`iceberg`, `delta`, `hudi`, `parquet`). Replace with your table writer using the same row dicts. |
| Streaming (Kafka / Kinesis) | `python/streaming_config_and_orchestrator_demo.py` | Validates `FactSourceSpec` + `EngineConfig` + micro-batch **rule refresh**; does not start a broker consumer. |
| KIE-compatible REST | `python/kie_rest_migration_recipe_demo.py` | `PUT` deploy + `POST` stateless execute against `/kie-server/services/rest/...`. |
| Governance promotion pins | `python/governance_promotion_pins_demo.py` | `sync_dev_from_active` + adjacent `promote` calls on `PromotionRegistry`. |
| Two-pass / `group_by` | `python/two_pass_orchestrator_demo.py` | Pass1 qualify, Pass2 with per-group quota + aggregate counts. |
| UDF registry | `python/udf_registry_demo.py` | Versioned resolve + `eval_registered_pure_udf` (`sum` / `len` bodies). |
| OPA / Ranger clients | `python/policy_opa_ranger_demo.py` | Live `query_opa` when `SPARKRULES_OPA_URL` is set; `ranger_allow_stub` local vs HTTP modes. |
| Time-travel debug replay | `python/time_travel_debug_api_demo.py` | FastAPI `TestClient` against capture + replay endpoints (same as production routes). |
| LSP / editor diagnostics | `python/lsp_analyze_drl_demo.py` | In-process `analyze_drl_for_lsp`; wire the function into your LSP server or extension. |
| Chaos / perf harness | `python/chaos_and_perf_harness_demo.py` | `ChaosPolicy` retry paths + `run_perf_harness` / `scale_evidence`. |
| AI rule suggestions | `python/ai_rule_suggestion_workflow_demo.py` | Offline `StubAiProvider`; set `SPARKRULES_AI_PROVIDER=openai` + key for generative path. |

## dbt integration

| Example | What it demonstrates |
|---------|---------------------|
| [dbt_clinical/](dbt_clinical/) | dbt + DuckDB staging for clinical lab data |
