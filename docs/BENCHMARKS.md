# Scale and benchmarks

This project includes **harnesses** to reason about very large runtimes, not live billion-row runs checked into Git.

## In-repo tools

- `sparkrules.runtime.perf.run_perf_harness`  -  measures elapsed time and rows/sec for a callable.
- `sparkrules.runtime.perf.scale_evidence`  -  produces a structured estimate (rows, rows/sec, target rows, estimated duration) for documentation and SLO planning.
- `sparkrules.obs.health`  -  classifies per-stage health from duration, shuffle volume, and task failures (for UI and ops dashboards).

## Default API path: not distributed Spark

For **default** HTTP simulations and the Workbench **Simulate** view, evaluation runs in **pure Python** in the API process: **`SparkSession.getActiveSession()` is typically `None`**, and there is **no** automatic `mapPartitions` / **broadcast** rule package on a **DataFrame**. That is **by design** for a simple integration surface; it is **not** evidence of billion-row Spark throughput.

For architecture scope, execution paths, and the wiring needed for real cluster execution (`mapPartitions`, `CompiledRulePackage` broadcast, `sparkrules/spark/dataframe.py`), see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md#execution-architecture). For **when to choose Spark** vs staying on Python, see [SPARK_INTEGRATION.md](SPARK_INTEGRATION.md).

## What “production evidence” means

A real **billions-of-rows** proof requires your Spark cluster, storage (Iceberg/Delta/Hudi/Parquet), and network. Capture:

1. **Job config**: merged `EngineConfig` / `runtime_conf()` and Spark versions.
2. **Input size**: row count, partition count, and format.
3. **Metrics**: stage duration, shuffle read/write, executor skew (Spark UI or your metrics store).
4. **Outcome**: end-to-end runtime and cost.

Store those artifacts in your internal wiki or data platform; the repository stays vendor-neutral.

## Reproducible local checks

Run the full test suite and coverage gate:

```bash
python -m pip install -e ".[test]"
python -m pytest tests/unit/ --cov=src/sre
```

Opt-in performance tests (if present) use `pytest -m perf`.

## Phase 4  -  lakehouse benchmarks

For **governance and promotion** (see [GOVERNANCE.md](GOVERNANCE.md)), the repository documents behavior only; your **lakehouse** is where you prove **latency and cost** for rule evaluation at scale.

1. **Baseline**: same `EngineConfig` / `runtime_conf()` and Spark version you use in production.
2. **Data**: one or more Iceberg/Delta/Parquet tables; record row counts, file sizes, and partition layout.
3. **Rule set**: a fixed namespace and promoted **prod** pin versions (or your packaging format).
4. **Run**: full job (or representative slice) with Spark UI and/or your metrics (Datadog, Databricks, etc.).
5. **Record**: job duration, shuffle GB, executor CPU, and cost estimate; file under your org’s performance evidence process.

Re-use the in-repo [perf harness](#in-repo-tools) for micro-benchmarks; lakehouse **billions-of-rows** evidence stays outside the repo, as in [What “production evidence” means](#what-production-evidence-means).
