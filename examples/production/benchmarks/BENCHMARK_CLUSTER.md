# Cluster benchmark protocol (1B+ rows)

Local `local[4]` numbers are useful for **regression** only. This document defines how to produce **comparable** evidence on a **large** Spark cluster (EMR, Databricks, or GKE / EKS with Spark operator).

## 1. Preconditions

- **Pinned** `sparkrules` version and **identical** DRL text as used in prod candidate.
- **Input format**: Parquet or Iceberg; **snappy** or **zstd** compression documented.
- **Partitioning**: fact table partitioned by columns documented (e.g. `tenant_id`, `dt`).
- **Cluster topology**: worker instance type, count, Spark `spark.sql.shuffle.partitions`, executor memory.

## 2. Workloads

| ID | Description | Success metric |
|----|-------------|----------------|
| A | Batch scoring: `SparkRuleExecutor.from_drl(drl).apply(df)` on full snapshot | Wall time, **p95 task** duration, shuffle read GB |
| B | Streaming micro-batch (see streaming example) sustained 30 min | **Input rows/s**, **end-to-end latency** p99 |
| C | Worst-case **PYTHON_FALLBACK** pack (intentionally non-pushdown) | Same as A — establishes upper bound |

## 3. Procedure

1. **Cold run** — discard first job (JVM warmup, codegen cache).
2. **Warm runs** — at least **3** consecutive runs; report median and stdev.
3. **Spark UI** — export stages page PNG or JSON for longest stage.
4. **GC** — note if G1 pause > 200 ms frequent (attach GC logs).

## 4. Reporting table (copy into PR)

| Field | Value |
|-------|-------|
| Date (UTC) | |
| Cloud + region | |
| Spark version | |
| sparkrules version | |
| Workers (count × type) | |
| Input rows | |
| Rule count / RulePack strategies | |
| Wall clock (median s) | |
| Cost (DBU or $ estimate) | |
| Notes (pushdown %, OOM, retries) | |

## 5. Honesty clause

If you have **not** run at 200+ nodes, state: **“projection from smaller cluster”** and list extrapolation assumptions. Prefer a **single** real large run over modeled numbers.

## 6. Automation hook

Optional: wrap `examples/python/benchmark_v2_local_throughput.py` ideas in a **PySpark** driver that writes CSV summaries to S3; keep driver code in your infra repo (secrets, endpoints).
