# Operator Runbook — Kafka → Spark Structured Streaming → Iceberg

**Author:** Ram Ghadiyaram  
**Pipeline version:** 1.0.0  
**Status:** Production-ready reference

This document accompanies the hardened streaming job  
`examples/streaming/kafka_iceberg_structured_streaming.py`.

---

## 1. Architecture overview

```
Kafka topic (facts)
        │
        ▼
Spark Structured Streaming (micro-batch)
        │
        ├─ parse JSON → structured fact
        ├─ apply_drl (SparkRules V2)
        ├─ enrich audit columns
        │
        ├─ success → Iceberg table (facts_scored)
        └─ failure → Iceberg DLQ  (facts_dlq)
```

Key design choices:

- **foreachBatch** – gives full control over scoring and dual-write (success + DLQ).
- **Checkpointing** – required for exactly-once semantics with Kafka source.
- **merge-schema** – allows additive audit columns without breaking existing tables.
- **No JVM inside the rule engine** – SparkRules stays pure-Python / V2 on executors.

---

## 2. Prerequisites

| Component | Version / note |
|-----------|----------------|
| Apache Spark | 3.5.x recommended |
| Iceberg runtime | `org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2` (or newer) |
| Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1` |
| SparkRules | `pip install 'sparkrules[spark]'` (or the version under test) |
| Python | 3.11+ |

---

## 3. Local development (Docker Compose)

```bash
cd examples/streaming   # or the PR folder
docker compose up -d

# wait until Kafka is healthy
docker compose ps

# publish sample traffic
python producer/sample_producer.py --count 40 --bootstrap localhost:9092

# submit the job (adjust packages for your Spark version)
spark-submit \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.local.type=hadoop \
  --conf spark.sql.catalog.local.warehouse=s3a://warehouse/ \
  --conf spark.hadoop.fs.s3a.endpoint=http://localhost:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
  kafka_iceberg_structured_streaming.py
```

MinIO console: http://localhost:9001 (minioadmin / minioadmin)

---

## 4. Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Comma-separated brokers |
| `KAFKA_TOPIC` | `facts` | Source topic |
| `KAFKA_STARTING_OFFSETS` | `latest` | `earliest` / `latest` / JSON offsets |
| `CHECKPOINT_DIR` | `/tmp/sparkrules-ckpt` | Must be durable in production (S3/HDFS/ADLS) |
| `ICEBERG_CATALOG` | `local` | Catalog name registered in Spark |
| `ICEBERG_OUTPUT_TABLE` | `local.db.facts_scored` | Success sink |
| `ICEBERG_DLQ_TABLE` | `local.db.facts_dlq` | Dead-letter sink |
| `SPARKRULES_DRL_PATH` | (bundled loan_underwriting.drl) | Path to DRL file |
| `TRIGGER_INTERVAL` | `10 seconds` | Micro-batch trigger |
| `MAX_OFFSETS_PER_TRIGGER` | `10000` | Back-pressure control |

---

## 5. Exactly-once & failure semantics

1. **Checkpoint location must be durable** and unique per job instance.
2. Kafka source + checkpoint = at-least-once by default; combined with idempotent Iceberg writes (or MERGE) you can achieve effective exactly-once for the scored table.
3. A failed micro-batch is logged; the stream continues. Parse failures go to the DLQ table.
4. On restart the job resumes from the last successful checkpoint offset.

**Recommended production settings:**

```bash
--conf spark.sql.streaming.checkpointLocation=s3a://my-bucket/checkpoints/sparkrules-loan
--conf spark.sql.streaming.minBatchesToRetain=10
--conf spark.streaming.kafka.maxRatePerPartition=2000
```

---

## 6. Monitoring

- Spark UI → Streaming tab (batch duration, input rate, processing time)
- Iceberg table history: `SELECT * FROM local.db.facts_scored.history`
- DLQ volume is a leading indicator of schema drift or poison messages
- Application logs emit structured JSON on batch errors

Suggested Prometheus metrics (if you expose them via a sidecar or Spark metrics system):

- `sparkrules_batch_rows_total`
- `sparkrules_batch_errors_total`
- `sparkrules_dlq_rows_total`
- `sparkrules_scoring_latency_seconds`

---

## 7. Schema evolution

The job uses `merge-schema=true` on both success and DLQ tables.  
Additive columns (new audit fields) are safe.  
Removing or changing type of existing columns requires a migration (new table or explicit ALTER).

---

## 8. Security notes

- Never embed credentials in the job code.
- Prefer instance profiles / workload identity for S3/ADLS/GCS.
- Kafka SASL/SSL configuration is passed via standard Spark Kafka options (`kafka.sasl.*`, `kafka.security.protocol`, etc.).
- DRL files should be treated as code – store them in a versioned location and promote through environments.

---

## 9. Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Job starts then idle | No data / wrong topic / `startingOffsets=latest` | Publish with producer or set `earliest` |
| PARSE_ERROR in DLQ | JSON shape mismatch | Align producer schema with `FACT_SCHEMA` |
| `Table does not exist` | Catalog / warehouse mis-configured | Verify `spark.sql.catalog.*` and warehouse path |
| Checkpoint conflict | Two jobs share same checkpoint dir | Use unique paths per job/version |
| Slow batches | Large `maxOffsetsPerTrigger` or complex DRL | Lower rate, increase executors, or broadcast compiled package |

---

## 10. Promoting to production

1. Replace local MinIO with your real Iceberg catalog (Glue, Nessie, Hive, REST).
2. Move checkpoint to durable object storage.
3. Pin SparkRules version and DRL version (use governance namespace if available).
4. Add canary / shadow traffic using the existing SparkRules shadow simulation APIs.
5. Wire alerts on DLQ growth and batch duration SLO breaches.

---

*Maintained by Ram Ghadiyaram – contributions welcome.*
