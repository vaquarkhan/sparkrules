# Deploy SparkRules in production

This runbook covers **Databricks**, **AWS Glue / EMR**, and **generic Spark on Kubernetes**. Adjust names (catalogs, VPCs, service principals) to your organization.

## 1. Roles and blast radius

| Surface | Trust boundary | Notes |
|---------|----------------|-------|
| FastAPI / Workbench | Internet or corp mesh | OIDC or mTLS; rate limits; audit every mutating route |
| Spark driver | Cluster admin | Holds DRL text and credentials; isolate per tenant where possible |
| Spark executors | Data plane | No outbound internet unless required; rule closures ship read-only |

## 2. Databricks

### 2.1 Cluster policy

- **Runtime**: DBR 14.3 LTS or newer with **Python 3.11** on the driver and workers.
- **Worker type**: memory-optimized (`r5d`, `r6id`) when closures retain large broadcast maps; otherwise general (`i3`, `m6i`).
- **Autoscaling**: start with **min workers = max workers** for reproducible latency SLOs; enable autoscale only after baseline.

### 2.2 DPU / worker sizing (starting point)

| Daily fact rows | Workers | DBU/hour (order of magnitude) | Notes |
|-----------------|---------|-------------------------------|-------|
| < 50M | 4–8 × m6i.xlarge | low | `local[4]` parity for dev |
| 50M–500M | 8–32 × r5.2xlarge | medium | Watch shuffle on wide facts |
| 500M–5B | 32–128 × r5.4xlarge+ | high | Prefer **SQL_PUSHDOWN** rules; profile Catalyst plans |
| 5B+ | 128–400+ | very high | Partition input by tenant; separate jobs per major tenant |

**Rule of thumb**: allocate **≥ 4 GiB executor heap** per million “wide” rows per stage if you rely on **PYTHON_FALLBACK**; SQL pushdown-heavy packs need far less.

### 2.3 Libraries

```text
%pip install 'sparkrules[spark,api]==<pinned>'
```

Pin a **single** version per job definition; promote only after [GOVERNANCE_WORKFLOW.md](GOVERNANCE_WORKFLOW.md) gates pass.

### 2.4 Unity Catalog / Iceberg

- Mount **read-only** DRL and metadata tables; writes go to **scored** tables per environment (`dev_scored`, `stage_scored`, `prod_scored`).
- Use **volume** or **Git folder** for DRL artifacts if you do not use the metadata API store.

### 2.5 Secrets

- Store Kafka passwords and catalog credentials in **Databricks secrets** scopes; reference with `{{secrets/scope/key}}` in Spark conf, never in notebooks committed to Git.

## 3. AWS Glue / EMR

### 3.1 Glue 4.0+

- Enable **Spark UI logs** and **job metrics** to S3.
- Set `--additional-python-modules=sparkrules==<pin>` (or wheel on S3).
- For Iceberg: pass `--datalake-formats=iceberg` and catalog AWS Glue settings per AWS docs.

### 3.2 EMR on EC2

- Use **EMR 6.12+** or **7.x** with same Python pin as CI.
- Place **Prometheus JMX exporter** on the master if you need JVM metrics alongside SparkRules `/metrics` from the API sidecar (if any).

## 4. Spark Streaming (Kafka → Iceberg)

See [../streaming/README.md](../streaming/README.md) and the reference job. Operational checklist:

1. **Checkpoint** location on durable object storage (S3 / ADLS), exclusive per job id.
2. **Exactly-once** requires transactional sink + idempotent producer settings on Kafka writes (if you echo results back).
3. **Rule refresh**: reload DRL on a schedule inside `foreachBatch` or via control topic; cap `max_rulepack_bytes` on the API path that publishes DRL.

## 5. API deployment (Kubernetes)

- Run **two** containers if you split metrics: app + optional `metrics` sidecar scraping `snapshot_engine_metrics` and exposing Prometheus format (not shipped by default in one process for engine-only metrics).
- **Liveness**: `GET /health` (if enabled in your build).
- **Readiness**: metadata store reachable + optional Kafka ping.

## 6. Rollback

- **Rules**: re-pin previous version via governance API or registry backup.
- **Binaries**: keep **N-2** container images in registry; Argo / Flux rollback to previous manifest.

## 7. Evidence for procurement

Attach outputs from [../benchmarks/BENCHMARK_CLUSTER.md](../benchmarks/BENCHMARK_CLUSTER.md) and SBOM from [SECURITY_SBOM.md](SECURITY_SBOM.md).
