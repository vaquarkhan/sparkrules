# Spark: optional by design

---

> **TL;DR — where Spark actually runs**
>
> | You are here | Spark used? |
> |--------------|-------------|
> | `POST /simulations`, Workbench **Simulate**, most **REST** traffic | **No** — pure **Python** in the API process (`SparkSession.getActiveSession()` is usually `None`). |
> | Your **PySpark job** calling **`apply_drl(df, drl)`** on a **`DataFrame`** | **Yes** — work is distributed by **Spark** (your cluster, your `SparkSession`). |
>
> **No server environment variable flips the API into Spark mode.** Integrate in code; see **`apply_drl`** below.

---

**SparkRules** is named for **Spark-oriented** data platforms, but **using Apache Spark (PySpark) is optional**. You choose the execution mode for your use case.

| Mode | When to use it | How rules run |
|------|----------------|---------------|
| **Pure Python (default API)** | Local development, `POST /simulations`, Workbench **Simulate**, fast feedback, CI | One **CPython** process; **no** `SparkSession` created by those endpoints. |
| **Spark-integrated (your job)** | Large **partitioned** tables, many executors, production lakehouse jobs | You build a `SparkSession`, apply rules on a **DataFrame** (see below); work runs on the **cluster**. |

There is **no** single `SPARKRULES_ENABLE_SPARK=true` switch that turns the **HTTP server** into a distributed Spark app. **Enabling Spark** means **writing (or reusing) a PySpark job** that calls the library, not only starting Uvicorn.

---

## When you do **not** need Spark

- Authoring, validating, and simulating rules via **`/rules/validate`**, **`/ide/lsp/analyze`**, **`/simulations`**, and the **Workbench** — all use the **in-process** engine.
- Unit tests and most integration tests.
- Scenarios where **one machine** and **Python throughput** are enough.

This is **normal** and **expected**; it does not mean the product is “broken.”

---

## When you **do** use Spark (PySpark)

Use Spark when you need **distributed** execution over **large** row sets already in the Spark ecosystem:

1. **Create** a `SparkSession` in **your** driver (EMR, Databricks, Dataproc, YARN, Kubernetes, etc.).
2. **Load** facts as a `DataFrame` (e.g. from Parquet, Iceberg, Delta — your catalog and IAM).
3. **Apply** DRL to that DataFrame using the helpers in `src/sre/spark/dataframe.py`:
   - **`apply_drl(df, drl, ...)`** — `broadcast`’s the DRL string, uses **`mapPartitions`** over the DataFrame’s RDD, returns a new `DataFrame` of `fact_id`, `fired`, `out_json`.
   - Lower-level: **`iter_rule_rows`**, **`mpartition_rows`** for custom pipelines.
4. **Optionally** combine with a **`CompiledRulePackage`** and **`sre/transport/broadcaster.py`** for **broadcasting** larger artifacts in advanced setups (see that module’s docstring and tests).

**Requirements on the workers:** JARs / Python environment must include this package, PySpark, and compatible Spark version — same as any other PySpark app.

---

## Relationship to the REST API

- The **FastAPI** process (`uvicorn`, Docker, etc.) is **separate** from a **batch Spark job**. You typically **do not** run the cluster inside the same process as `/simulations`.
- You **can** use the API to **govern and store** rules, then your Spark job **loads** the DRL (or package) and calls `apply_drl` or the executor path you design.

For **claim-level** honesty about default paths and throughput, see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md#spark-and-distributed-execution) and [BENCHMARKS.md](BENCHMARKS.md).

---

## Quick reference (code)

| Component | Path |
|-----------|------|
| DataFrame DRL application | `sre/spark/dataframe.py` — `apply_drl`, `iter_rule_rows`, `rows_from_session` |
| Broadcast bytes | `sre/transport/broadcaster.py` |
| **Runnable E2E samples** | [`examples/spark/`](../examples/spark/README.md) — `apply_drl_local.py` (PySpark + Java), `iter_rule_rows_no_jvm.py` (no JVM) |
| Spark iterator tests (need JVM) | `tests/spark/`, `tests/unit/test_spark_iter.py` |

If you are unsure, start with **pure Python** simulations; add **Spark** when you have a real **DataFrame** and a **cluster** to run on.

---

## Tests and line coverage (`src/sre/spark`)

The **`sre.spark`** package is covered to **100% line** coverage in CI style when you run:

```bash
python -m pytest tests/unit/ -q --cov=src/sre
```

How that is achieved:

| Test file | What it covers |
|-----------|----------------|
| `tests/unit/test_spark_iter.py` | `iter_rule_rows` with **dict** rows and row-like `asDict()` (no JVM). |
| `tests/unit/test_cov_spark_apply_mocks.py` | `apply_drl` with a **mock** `DataFrame` / `SparkSession` (no JVM), `rows_from_session`, and non-dict partition elements. |
| `tests/unit/test_cov_spark_mpartition.py` | `mpartition_rows` with real **PySpark** `Row` (imports `pyspark`; skipped if import fails). |
| `tests/spark/test_pyspark_dataframe.py` | Optional **end-to-end** with `SparkSession` (`local[1]`) — **requires JVM**; marked `spark`, not in default `pytest` selection if you exclude the directory. |

You get **full** `sre/spark` coverage from **unit** tests alone (mocks + `importorskip` PySpark for `mpartition_rows`); the `tests/spark/` file is for **real** Spark smoke runs in environments with Java.
