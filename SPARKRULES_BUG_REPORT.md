# SparkRules bug register (forensics)

**Audience:** Engineering sign-off, PM risk review, external auditors.  
**Normative requirements:** [docs/REQUIREMENTS_V2_ENGINE.md](docs/REQUIREMENTS_V2_ENGINE.md) (Req 1–37).  
**Scope:** V2 compiler, translators, executors (local / pandas / Spark), metrics, examples, packaging.

**Legend:** **Fixed** = addressed in `main` with unit tests; **Partial** = mitigated or documented; **Open** = still tracked; **Spark-verify** = needs JVM PySpark cluster to fully validate.

---

## Summary table (23 items)

| # | Severity | Topic | Status | Primary surface |
|---|----------|-------|--------|-----------------|
| 1 | HIGH | Pickle RCE / unsafe `RulePack.deserialize` | **Fixed** | `compiler/safe_pickle.py`, `rulepack.py`, `tests/unit/test_rulepack_pickling_security.py` |
| 2 | HIGH | SQL string literal escaping (`''`) | **Fixed** | `compiler/translator.py` |
| 3 | HIGH | `CONTAINS` Python vs Spark / Rete / evaluator drift | **Fixed** | `closure.contains_semantics`, `rete.py`, `evaluator.py`, `translator.py` (null-safe CASE) |
| 4 | HIGH | Strategy C actions ignored `ast.then` (empty `action_sql`) | **Fixed** | `spark/executor.py` (`_action_fields_from_ast`), `rulepack.py` ALPHA `action_sql` fill |
| 5 | HIGH | Cross-strategy `COALESCE` type mismatch on merged actions | **Fixed** | `executor._merge_actions` casts to `StringType`; `action_staging_merge_plan` |
| 6 | HIGH | Strategy B duplicate alpha planning / O(N²) | **Fixed** | `spark/executor.py` |
| 7 | MEDIUM | `IN` with non-list column RHS | **Fixed** | `translator.py` → `array_contains(rhs, left)` |
| 8 | MEDIUM | `MATCHES` / RLIKE vs Python `re` divergence | **Partial** | `_spark_rlike_pattern_literal`, `_has_python_only_regex`, `docs/KNOWN_LIMITATIONS.md` |
| 9 | MEDIUM | Hyphenated `activation-group` / `agenda-group` tokens | **Fixed** | `parser/lexer.py` |
| 10 | MEDIUM | Pandas path rewriting `AND` inside string literals | **Fixed** | `pandas_executor.py` |
| 11 | MEDIUM | `translation_failures_total` undercount | **Fixed** | `rulepack.py` (classify + ALPHA build paths), `engine_metrics.py` |
| 12 | MEDIUM | Docs / scripts still referenced `sre` / `src/sre` | **Fixed** | `docs/*.md`, `deploy/*`, `examples/spark/DROOLS_FEATURES.md` |
| 13 | MEDIUM | README / FEATURES ↔ KNOWN_LIMITATIONS discoverability | **Fixed** | `README.md`, `docs/FEATURES.md` |
| 14 | MEDIUM | `pip install sparkrules` + uvicorn cryptic error | **Fixed** | `api/_http_deps.py` |
| 15 | LOW | Spark `tests/spark/test_pyspark_dataframe.py` MapType vs StructType | **Fixed** | Explicit `StructType` for nested facts; legacy test name retained |
| 16 | LOW | Use-case `spark_e2e.py` still on V1-style columns | **Fixed** | `examples/usecases/*/spark_e2e.py` (`fired_any`, `Row` structs) |
| 17 | LOW | `LocalRuleExecutor` unpickle / joblib ergonomics | **Fixed** | `local_executor.py` |
| 18 | LOW | dbt clinical example missing `schema.yml` | **Fixed** | `examples/dbt_clinical/models/schema.yml`, `seeds/schema.yml` |
| 19 | LOW | Five `# pragma: no cover` on Spark executor methods | **Open** | `spark/executor.py` — unit CI has no JVM; `action_staging_merge_plan` is covered without Spark |
| 20 | MEDIUM | Clinical / dbt column casing (`glucose_pref_mgdL`, etc.) | **Fixed** | `examples/usecases/clinical_research/*`, `examples/dbt_clinical/*` |
| 21 | HIGH | `contains` null propagation in Spark CASE | **Fixed** | `translator.py` (`IS NULL`, `coalesce` on `instr` branch) |
| 22 | MEDIUM | FastAPI `E402` / import order in `app.py` | **Fixed** | `api/_http_deps.py` |
| 23 | Spark-verify | End-to-end Strategy A/B/C on real Catalyst | **Spark-verify** | Run `examples/spark/apply_drl_local.py` and use-case `spark_e2e.py` with Java on CI |

---

## Forensics (condensed)

### 1 — Restricted unpickling
**Symptom:** `pickle.loads` on untrusted bytes = arbitrary code execution.  
**Fix:** `safe_pickle.loads_rulepack_payload`, env `SPARKRULES_RULEPACK_UNSAFE_PICKLE`, tests for allowlist.

### 3 — `CONTAINS` three-way drift
**Symptom:** Rete used `_t in v if hasattr(v,"__contains__")`; strings matched substring but **dicts** fell through to wrong branch vs `closure._compare`. Evaluator used `str(b) in str(a)` for non-lists → **dict** wrong.  
**Fix:** Single `contains_semantics()` in `closure.py`; Rete + evaluator import it; Spark SQL adds null-safe guards.

### 4–5 — Strategy C + merge
**Symptom:** PYTHON_FALLBACK rules produced no typed action columns from SQL dict; merge mixed numeric SQL expr with string Strategy C columns → Catalyst errors.  
**Fix:** AST-driven fields; `StringType()` coalesce path; pure `action_staging_merge_plan()` for ordering tests.

### 7 — `IN` column RHS
**Symptom:** Translator raised `TranslationError`.  
**Fix:** Emit `array_contains(array_col, value)`; document RHS must be array-typed in Spark.

### 8 — Regex flavors
**Symptom:** Python `re.search` vs Spark `RLIKE` (Java regex).  
**Mitigation:** Backslash doubling for literals; `_has_python_only_regex` pushes lookaround to PYTHON_FALLBACK; limitations doc.

### 11 — Metrics
**Symptom:** Silent SQL downgrade paths did not increment counter.  
**Fix:** `record_translation_failure()` when predicate is not `can_translate`, when ALPHA action SQL fill fails, existing executor alpha translate failures.

### 15 — MapType schema
**Symptom:** `createDataFrame([{z: {n:1}}])` → `MapType`; V2 executor rejects.  
**Fix:** Tests and examples use `StructType` / `Row` nesting.

### 19 — Pragma coverage
**Symptom:** 100% line coverage on `src/sparkrules` while Spark methods untested in CI without JVM.  
**Mitigation:** `action_staging_merge_plan` covered in unit tests; full `apply()` remains integration-tested.

---

## Sign-off checklist

- [ ] Run `pytest tests/unit/ --cov=sparkrules` (100% gate).  
- [ ] Run `pytest tests/spark/` on a JVM host (Spark-verify bucket).  
- [ ] Re-read [docs/REQUIREMENTS_V2_ENGINE.md](docs/REQUIREMENTS_V2_ENGINE.md) §2 non-goals and Req 30–37 for rollout/security/memory.
