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

---

## Performance on Spark, and where Glue / workers / DPU are defined

**What the library does for performance**

- `apply_drl` **broadcasts** the DRL string and uses **`mapPartitions`**, so each partition parses once per task and evaluates rows in bulk — that is the main in-repo pattern for distributed throughput.
- **Tuning** (partitions, shuffle, AQE, executor size) is **standard Spark** on **your** cluster: the examples use `local[2]` only; production jobs set `--conf` / job parameters in **Glue, Databricks, Dataproc**, etc.

**Where “worker size / DPU / Glue vs Databricks” live in *this* repo**

They are modeled as **`EngineConfig`** and the derived map from **`runtime_conf()`** in:

- `src/sre/runtime/config_contract.py` — fields include `platform` (`local`, `glue`, `databricks`, `gcp-dataproc`, `azure-synapse`), `executor_cores`, `executor_workers`, `executor_memory_gb`, and **`glue_dpu`** (used when `platform == "glue"`), plus `spark_version` normalization.

That is a **zero-code-change config contract** for *documenting* what a deployment should use; it does **not** automatically reconfigure a running `SparkSession` in the examples. Your **Glue job** or **Databricks cluster** is where you set real DPU / workers / `spark.*` in practice.

- **Read-only view in the API:** `GET /system/deployment` returns a map built from a **default** `EngineConfig()` (see `sre.api.app`); adjust behavior in a custom deployment by using `AppDeps.engine_cfg` or your own process’ env — the stock server is illustrative.

- **Cloud how-tos:** [deploy/README.md](../../deploy/README.md) and subfolders `deploy/aws-glue/`, `deploy/databricks/`, etc.
