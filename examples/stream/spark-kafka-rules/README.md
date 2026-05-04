# Spark + Kafka + SparkRules

Structured Streaming reads JSON fact payloads from Kafka, parses them as fact `T`, and scores with **`apply_drl`** using the DRL pack in **`rules/ingress.drl`**.

## Layout

| Path | Description |
|------|-------------|
| `rules/ingress.drl` | Example rules (amount / velocity style checks) |
| `spark_kafka_structured_streaming.py` | PySpark driver (no Iceberg required for the minimal path) |

## Quick local check (Kafka running)

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_TOPIC=facts
export CHECKPOINT_DIR=/tmp/sparkrules-ckpt-stream
export SPARKRULES_DRL_PATH="$(pwd)/rules/ingress.drl"
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 spark_kafka_structured_streaming.py
```

For **checkpoint on S3** in AWS, set `CHECKPOINT_DIR=s3a://bucket/prefix/ckpt` and configure Hadoop S3A credentials.

## Output

The sample job writes **Parquet** (or path from `STREAM_OUTPUT_PATH`) per micro-batch. Replace with your sink (Iceberg, Delta, JDBC) using the same `scored` DataFrame.

## Requirements

- `pip install 'sparkrules[spark]'` on driver and executors (same version).
- Spark SQL Kafka JAR (via `--packages` as above).
