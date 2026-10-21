#!/usr/bin/env python3
"""
Kafka → Spark Structured Streaming → Iceberg production pipeline
with SparkRules V2 scoring and full audit trail.

Author: Ram Ghadiyaram
Date: 2026-10

Closes the gap in docs/PENDING_NON_BLOCKING.md
("Full Kafka → Spark → Iceberg runnable job").

Follows the official SparkRules pattern from:
  examples/streaming/kafka_iceberg_structured_streaming.py
  examples/streaming/spark_structured_streaming_rate_simulator.py

Key design (matches upstream):
  - Parse Kafka JSON into a struct column named ``t``
  - apply_drl(df, drl, use_v2=True) → original cols + action_* + fired_any
  - CREATE TABLE IF NOT EXISTS before first append
  - Dead-letter table for parse failures

Usage (local Docker Compose)
----------------------------
    docker compose up -d
    python producer/sample_producer.py --count 30

    spark-submit \\
      --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2,\\
                 org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \\
      --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \\
      --conf spark.sql.catalog.local=org.apache.iceberg.spark.SparkCatalog \\
      --conf spark.sql.catalog.local.type=hadoop \\
      --conf spark.sql.catalog.local.warehouse=s3a://warehouse/ \\
      --conf spark.hadoop.fs.s3a.endpoint=http://localhost:9000 \\
      --conf spark.hadoop.fs.s3a.access.key=minioadmin \\
      --conf spark.hadoop.fs.s3a.secret.key=minioadmin \\
      --conf spark.hadoop.fs.s3a.path.style.access=true \\
      --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \\
      kafka_iceberg_structured_streaming.py

Environment variables
---------------------
    KAFKA_BOOTSTRAP_SERVERS   default: localhost:9092
    KAFKA_TOPIC               default: facts
    KAFKA_STARTING_OFFSETS    default: latest
    CHECKPOINT_DIR            default: /tmp/sparkrules-ckpt
    ICEBERG_CATALOG           default: local
    ICEBERG_OUTPUT_TABLE      default: local.db.facts_scored
    ICEBERG_DLQ_TABLE         default: local.db.facts_dlq
    SPARKRULES_DRL_PATH       path to .drl (defaults to rules/loan_underwriting.drl)
    TRIGGER_INTERVAL          default: 10 seconds
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

_DRL_CACHE: list[str] = []

# Fact schema for Kafka JSON → struct column ``t``
# Must align with DRL field references ($t.amount, $t.credit_score, ...)
FACT_SCHEMA = (
    "struct<"
    "application_id:string,"
    "amount:bigint,"
    "credit_score:int,"
    "region:string,"
    "product:string,"
    "applicant_age:int,"
    "event_ts:string"
    ">"
)


def _env(key: str, default: str | None = None) -> str:
    val = os.environ.get(key, default)
    if val is None:
        raise RuntimeError(f"Required environment variable {key} is not set")
    return val


def _load_drl() -> str:
    """Load DRL once and cache."""
    if _DRL_CACHE:
        return _DRL_CACHE[0]

    path = (os.environ.get("SPARKRULES_DRL_PATH") or "").strip()
    if path and Path(path).is_file():
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = os.environ.get(
            "SPARKRULES_DRL",
            'rule "fallback" when $t : T( $t.amount > 0 ) '
            'then result.decision = "APPROVE"; result.reason_code = "OK"; end',
        )
    _DRL_CACHE.append(text)
    return text


def _build_spark() -> "SparkSession":
    from pyspark.sql import SparkSession

    checkpoint = _env("CHECKPOINT_DIR", "/tmp/sparkrules-ckpt")
    catalog = _env("ICEBERG_CATALOG", "local")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE", "s3a://warehouse/")

    spark = (
        SparkSession.builder.appName("sparkrules-kafka-iceberg-loan")
        .config("spark.sql.streaming.checkpointLocation", checkpoint)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .getOrCreate()
    )

    # Apply local catalog fallback only when not already configured via --conf
    existing = spark.conf.get(f"spark.sql.catalog.{catalog}", None)
    if not existing:
        spark.conf.set(
            f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog"
        )
        spark.conf.set(f"spark.sql.catalog.{catalog}.type", "hadoop")
        spark.conf.set(f"spark.sql.catalog.{catalog}.warehouse", warehouse)

    return spark


def _ensure_table(spark: "SparkSession", table: str, ddl_columns: str) -> None:
    """Create Iceberg table if it does not exist (idempotent)."""
    spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({ddl_columns}) USING iceberg")


def _safe_action_col(scored: "DataFrame", action_name: str, alias: str):
    """Return a Column for action_<name> if present, else null string."""
    from pyspark.sql import functions as F

    col_name = f"action_{action_name}"
    if col_name in scored.columns:
        return F.col(col_name).alias(alias)
    return F.lit(None).cast("string").alias(alias)


def _safe_bool_col(scored: "DataFrame", col_name: str, alias: str):
    """Return a boolean Column if present, else lit(False)."""
    from pyspark.sql import functions as F

    if col_name in scored.columns:
        return F.col(col_name).alias(alias)
    return F.lit(False).alias(alias)


def _score_batch(df: "DataFrame", batch_id: int) -> None:
    """Score one micro-batch: parse → apply_drl (V2) → Iceberg success + DLQ."""
    from pyspark.sql import functions as F
    from sparkrules.spark import apply_drl

    drl = _load_drl()
    catalog = _env("ICEBERG_CATALOG", "local")
    out_table = _env("ICEBERG_OUTPUT_TABLE", f"{catalog}.db.facts_scored")
    dlq_table = _env("ICEBERG_DLQ_TABLE", f"{catalog}.db.facts_dlq")
    spark = df.sparkSession

    # Ensure tables exist before first write
    _ensure_table(
        spark,
        out_table,
        """
        application_id STRING,
        amount BIGINT,
        credit_score INT,
        region STRING,
        product STRING,
        applicant_age INT,
        event_ts STRING,
        kafka_key STRING,
        kafka_partition INT,
        kafka_offset BIGINT,
        batch_id INT,
        scored_at STRING,
        pipeline_version STRING,
        decision STRING,
        reason_code STRING,
        risk_tier STRING,
        fired_any BOOLEAN
        """,
    )
    _ensure_table(
        spark,
        dlq_table,
        """
        raw_value STRING,
        kafka_key STRING,
        topic STRING,
        partition INT,
        offset BIGINT,
        kafka_ts TIMESTAMP,
        error_type STRING,
        batch_id INT,
        dlq_ts STRING
        """,
    )

    # 1. Kafka metadata + parse value into struct column ``t``
    #    Official pattern: .alias("t") so DRL `$t : T(...)` binds correctly.
    with_meta = df.select(
        F.col("key").cast("string").alias("kafka_key"),
        F.col("topic"),
        F.col("partition").alias("kafka_partition"),
        F.col("offset").alias("kafka_offset"),
        F.col("timestamp").alias("kafka_ts"),
        F.col("value").cast("string").alias("raw_value"),
        F.from_json(F.col("value").cast("string"), FACT_SCHEMA).alias("t"),
    )

    good = with_meta.filter(F.col("t").isNotNull())
    bad = with_meta.filter(F.col("t").isNull())

    # 2. DLQ for parse failures
    if not bad.isEmpty():
        bad.select(
            F.col("raw_value"),
            F.col("kafka_key"),
            F.col("topic"),
            F.col("kafka_partition").alias("partition"),
            F.col("kafka_offset").alias("offset"),
            F.col("kafka_ts"),
            F.lit("PARSE_ERROR").alias("error_type"),
            F.lit(batch_id).alias("batch_id"),
            F.lit(datetime.now(timezone.utc).isoformat()).alias("dlq_ts"),
        ).writeTo(dlq_table).option("merge-schema", "true").append()

    if good.isEmpty():
        return

    # 3. apply_drl on struct column ``t`` only (matches upstream rate + kafka examples)
    facts = good.select(F.col("t"))
    scored = apply_drl(facts, drl, use_v2=True)

    # 4. Flatten fact fields + V2 action columns + fired_any
    #    V2 wide format: action_decision, action_reason_code, action_risk_tier, fired_any
    scored_flat = scored.select(
        F.col("t.application_id").alias("application_id"),
        F.col("t.amount").alias("amount"),
        F.col("t.credit_score").alias("credit_score"),
        F.col("t.region").alias("region"),
        F.col("t.product").alias("product"),
        F.col("t.applicant_age").alias("applicant_age"),
        F.col("t.event_ts").alias("event_ts"),
        _safe_bool_col(scored, "fired_any", "fired_any"),
        _safe_action_col(scored, "decision", "decision"),
        _safe_action_col(scored, "reason_code", "reason_code"),
        _safe_action_col(scored, "risk_tier", "risk_tier"),
    )

    # 5. Join Kafka metadata back on application_id (stable, no positional zip)
    meta = good.select(
        F.col("t.application_id").alias("application_id"),
        F.col("kafka_key"),
        F.col("kafka_partition"),
        F.col("kafka_offset"),
    )

    final_df = (
        scored_flat.join(meta, on="application_id", how="left")
        .withColumn("batch_id", F.lit(batch_id))
        .withColumn("scored_at", F.lit(datetime.now(timezone.utc).isoformat()))
        .withColumn("pipeline_version", F.lit("1.0.0-ram-ghadiyaram"))
        .select(
            "application_id",
            "amount",
            "credit_score",
            "region",
            "product",
            "applicant_age",
            "event_ts",
            "kafka_key",
            "kafka_partition",
            "kafka_offset",
            "batch_id",
            "scored_at",
            "pipeline_version",
            "decision",
            "reason_code",
            "risk_tier",
            "fired_any",
        )
    )

    final_df.writeTo(out_table).option("merge-schema", "true").append()


def main(argv: list[str] | None = None) -> int:
    _ = argv

    os.environ.setdefault("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    os.environ.setdefault("KAFKA_TOPIC", "facts")
    os.environ.setdefault("KAFKA_STARTING_OFFSETS", "latest")
    os.environ.setdefault("CHECKPOINT_DIR", "/tmp/sparkrules-ckpt")
    os.environ.setdefault("ICEBERG_CATALOG", "local")
    os.environ.setdefault("ICEBERG_OUTPUT_TABLE", "local.db.facts_scored")
    os.environ.setdefault("ICEBERG_DLQ_TABLE", "local.db.facts_dlq")
    os.environ.setdefault("TRIGGER_INTERVAL", "10 seconds")

    default_drl = Path(__file__).resolve().parent / "rules" / "loan_underwriting.drl"
    if default_drl.is_file() and not os.environ.get("SPARKRULES_DRL_PATH"):
        os.environ["SPARKRULES_DRL_PATH"] = str(default_drl)

    bootstrap = _env("KAFKA_BOOTSTRAP_SERVERS")
    topic = _env("KAFKA_TOPIC")
    checkpoint = _env("CHECKPOINT_DIR")
    trigger = _env("TRIGGER_INTERVAL", "10 seconds")

    try:
        spark = _build_spark()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "hint": (
                        "PySpark + Iceberg + Kafka packages required. "
                        "pip install 'sparkrules[spark]' and pass --packages on spark-submit."
                    ),
                },
                indent=2,
            )
            + "\n"
        )
        return 1

    catalog = _env("ICEBERG_CATALOG", "local")
    try:
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.db")
    except Exception:  # noqa: BLE001
        pass

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", _env("KAFKA_STARTING_OFFSETS", "latest"))
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", os.environ.get("MAX_OFFSETS_PER_TRIGGER", "10000"))
        .load()
    )

    def foreach_batch(batch_df: "DataFrame", batch_id: int) -> None:
        if batch_df.isEmpty():
            return
        try:
            _score_batch(batch_df, batch_id)
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "level": "ERROR",
                        "batch_id": batch_id,
                        "error": str(exc),
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                file=sys.stderr,
            )

    query = (
        raw.writeStream.foreachBatch(foreach_batch)
        .option("checkpointLocation", checkpoint)
        .trigger(processingTime=trigger)
        .start()
    )

    print(
        json.dumps(
            {
                "status": "STARTED",
                "topic": topic,
                "bootstrap": bootstrap,
                "checkpoint": checkpoint,
                "output_table": _env("ICEBERG_OUTPUT_TABLE"),
                "dlq_table": _env("ICEBERG_DLQ_TABLE"),
                "drl": os.environ.get("SPARKRULES_DRL_PATH", "<inline>"),
            },
            indent=2,
        )
    )

    query.awaitTermination()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
