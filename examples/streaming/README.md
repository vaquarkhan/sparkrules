# Kafka → Iceberg (Spark Structured Streaming)

| File | Description |
|------|-------------|
| [kafka_iceberg_structured_streaming.py](kafka_iceberg_structured_streaming.py) | Runnable **reference** job: read Kafka → `foreachBatch` → `apply_drl` → append Iceberg |

## Requirements

- JVM + **PySpark** on the classpath used by your cluster.
- `pip install 'sparkrules[spark]'` on the driver (same version as CI-tested).
- Iceberg Spark runtime JARs and catalog configuration (Glue, Hive, REST) per your platform.
- Kafka ACLs allowing the job’s principal to **consume** the facts topic.

## Operations

1. Set **checkpoint** path exclusively for this job (S3 / ADLS).
2. Tune `maxOffsetsPerTrigger` for back-pressure.
3. Reload DRL on a schedule inside `foreachBatch` or subscribe to a **rules** topic; keep packs under `SPARKRULES_MAX_RULEPACK_BYTES`.

The CLI helper `python -m sparkrules.tools.stream_kafka_iceberg` still prints a **plan JSON** only — use this folder for an executable streaming outline.
