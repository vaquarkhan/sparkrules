# PySpark (end-to-end) examples

These scripts show how **SparkRules** integrates with **PySpark**: rules run on a **`DataFrame`** in a `SparkSession`, not in the HTTP `/simulations` path.

Read first: [docs/SPARK_INTEGRATION.md](../../docs/SPARK_INTEGRATION.md).

---

## Lending portfolio (Drools-style DRL + CSV + scale)

Use this track to see **salience, agenda/activation, reason_codes, stop_on_fire**, and a **non-trivial `when`** (credit, capacity, state/product restrictions), on **tabular data** (same DRL style as Drools, evaluated in Spark with **broadcast + `mapPartitions`**).

| Path | Role |
|------|------|
| [**drools_lending_premium.drl**](drools_lending_premium.drl) | One rich DRL file: prime preferred tier (FICO, DTI, income, delinquency, product, restricted states). |
| [**data/lending_portfolio_sample.csv**](data/lending_portfolio_sample.csv) | 90 application rows: `id`, `annual_income`, `fico_score`, `dti`, `state`, `product`, `delinq_90d_12m`. |
| [**validate_lending_csv.py**](validate_lending_csv.py) | **No Java / no Spark** — loads CSV, builds nested fact `a`, runs **`iter_rule_rows`**. Run this first to validate the DRL and data **everywhere** (`python examples/spark/validate_lending_csv.py`). |
| [**lending_e2e.py**](lending_e2e.py) | **Full PySpark** — reads the same CSV (or **`--synthetic N`** for large deterministic rows), builds a **`struct` `a`**, **`apply_drl`**, reports **rows/sec** smoke. **Requires Java** + PySpark. |
| [**DROOLS_FEATURES.md**](DROOLS_FEATURES.md) | What from Drools is **in the file** vs what needs **chain / agenda** APIs. |

**Suggested order**

1. `python examples/spark/validate_lending_csv.py` — stock CSV should print `rules_fired=22` (matches vary if you regenerate the sample).
2. `python examples/spark/lending_e2e.py` — same CSV on Spark.
3. `python examples/spark/lending_e2e.py --synthetic 100000 --partitions 32` — throughput smoke (on a machine with working Spark).

**Performance:** huge data and cluster sizing are about **Spark partitions + executors** in **your** job; see [Performance on Spark…](#performance-on-spark-and-where-glue--workers--dpu-are-defined) below and [DROOLS_FEATURES.md](DROOLS_FEATURES.md).

---

## Prerequisites

1. **Install the package** from the repo root (includes **PySpark** in the `test` extra):

   ```bash
   python -m pip install -e ".[test]"
   ```

2. **JVM** — Spark needs Java. Install **JDK 17** (or the version your PySpark build expects) and, on Windows, ensure `java -version` works. If the VM fails to start, set `JAVA_HOME` to the JDK install path.

3. **Platform** — `local[*]` is enough for the samples; no YARN or cloud cluster is required for local runs.

---

## All scripts in this folder

| File | What it does |
|------|--------------|
| [**apply_drl_local.py**](apply_drl_local.py) | **Minimal E2E:** `SparkSession` → `rows_from_session` → **`apply_drl`** on [../drl/minimal.drl](../drl/minimal.drl). |
| [**iter_rule_rows_no_jvm.py**](iter_rule_rows_no_jvm.py) | **No JVM:** [minimal.drl](../drl/minimal.drl) through **`iter_rule_rows`**. |
| [**lending_e2e.py**](lending_e2e.py) | **Lending sample:** [drools_lending_premium.drl](drools_lending_premium.drl) + CSV or **synthetic** rows. |
| [**validate_lending_csv.py**](validate_lending_csv.py) | **No Spark:** validate lending DRL + **data/lending_portfolio_sample.csv**. |

## Run (quick)

From the **repository root**:

```bash
python examples/spark/validate_lending_csv.py
python examples/spark/iter_rule_rows_no_jvm.py
python examples/spark/apply_drl_local.py
python examples/spark/lending_e2e.py
```

If Spark startup fails, fix Java / `JAVA_HOME`, or rely on **`validate_lending_csv.py`** for a full rule+data check without Spark.

---

## Relation to `tests/spark/`

The project also has `tests/spark/test_pyspark_dataframe.py` (pytest, optional JVM). These **examples** are user-facing and runnable without pytest.

---

## Performance on Spark, and where Glue / workers / DPU are defined

**What the library does for performance**

- `apply_drl` **broadcasts** the DRL string and uses **`mapPartitions`**, so each partition parses once per task and evaluates rows in bulk — that is the main in-repo pattern for distributed throughput.
- **Tuning** (partitions, shuffle, AQE, executor size) is **standard Spark** on **your** cluster: the examples use `local[*]`; production jobs set `--conf` / job parameters in **Glue, Databricks, Dataproc**, etc.

**Where “worker size / DPU / Glue vs Databricks” live in *this* repo**

They are modeled as **`EngineConfig`** and the derived map from **`runtime_conf()`** in:

- `src/sre/runtime/config_contract.py` — fields include `platform` (`local`, `glue`, `databricks`, `gcp-dataproc`, `azure-synapse`), `executor_cores`, `executor_workers`, `executor_memory_gb`, and **`glue_dpu`** (when `platform == "glue"`), plus `spark_version` normalization.

That is a **zero-code-change config contract** for *documenting* what a deployment should use; it does **not** automatically reconfigure a running `SparkSession` in the examples. Your **Glue job** or **Databricks cluster** is where you set real DPU / workers / `spark.*` in practice.

- **Read-only view in the API:** `GET /system/deployment` returns a map built from a **default** `EngineConfig()`.

- **Cloud how-tos:** [deploy/README.md](../../deploy/README.md) and subfolders `deploy/aws-glue/`, `deploy/databricks/`, etc.
