# PySpark (end-to-end) examples

These scripts show how **SparkRules** integrates with **PySpark**: rules run on a **`DataFrame`** in a `SparkSession`, not in the HTTP `/simulations` path.

Read first: [docs/SPARK_INTEGRATION.md](../../docs/SPARK_INTEGRATION.md).

## Prerequisites

1. **Install the package** from the repo root (includes **PySpark** in the `test` extra):

   ```bash
   python -m pip install -e ".[test]"
   ```

2. **JVM** — Spark needs Java. Install **JDK 17** (or the version your PySpark build expects) and, on Windows, ensure `java -version` works. If the VM fails to start, set `JAVA_HOME` to the JDK install path.

3. **Platform** — `local[*]` / `local[2]` is enough for the samples; no YARN or cloud cluster is required.

## Scripts

| File | What it does |
|------|----------------|
| [**apply_drl_local.py**](apply_drl_local.py) | **Full E2E:** `SparkSession` → `rows_from_session` → **`apply_drl`** on [../drl/minimal.drl](../drl/minimal.drl) — prints `fact_id`, `fired`, JSON output. **Requires Java + PySpark.** |
| [**iter_rule_rows_no_jvm.py**](iter_rule_rows_no_jvm.py) | **No JVM:** same DRL and facts through **`iter_rule_rows`** only (this is the per-row logic Spark runs inside `mapPartitions`). For laptops without Java. |

## Run

From the **repository root**:

```bash
python examples/spark/iter_rule_rows_no_jvm.py
python examples/spark/apply_drl_local.py
```

If `apply_drl_local.py` fails on Spark startup, run `iter_rule_rows_no_jvm.py` to confirm the rule, then fix Java / `JAVA_HOME` and retry the PySpark example.

## Relation to `tests/spark/`

The project also has `tests/spark/test_pyspark_dataframe.py` (pytest, optional JVM). These examples are **user-facing** copies you can run ad hoc without pytest.
