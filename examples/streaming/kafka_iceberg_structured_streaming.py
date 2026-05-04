"""Kafka → Spark Structured Streaming → Iceberg, with SparkRules V2 scoring.

This is a **reference job** for operators. It is not executed in SparkRules CI (JVM + brokers required).

Usage (illustrative)::

    spark-submit \\
      --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \\
      kafka_iceberg_structured_streaming.py

Environment variables (examples)::

    KAFKA_BOOTSTRAP_SERVERS=broker1:9092,broker2:9092
    KAFKA_TOPIC=facts
    KAFKA_STARTING_OFFSETS=latest
    CHECKPOINT_DIR=s3a://bucket/checkpoints/sparkrules-facts
    ICEBERG_CATALOG=glue
    ICEBERG_WAREHOUSE=s3://bucket/warehouse/
    ICEBERG_OUTPUT_TABLE=analytics.facts_scored
    SPARKRULES_DRL_PATH=/mnt/rules/policy.drl

Edit Spark session builder below for your catalog (`spark.sql.catalog.*` confs).
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

_DRL_CACHE: list[str] = []


def _load_drl() -> str:
    if _DRL_CACHE:
        return _DRL_CACHE[0]
    path = os.environ.get("SPARKRULES_DRL_PATH", "")
    if path and os.path.isfile(path):
        text = open(path, encoding="utf-8").read()
    else:
        text = os.environ.get(
            "SPARKRULES_DRL",
            'rule "r" when $t : T ( $t.amount > 0 ) then result.ok = true; end',
        )
    _DRL_CACHE.append(text)
    return text


def _build_spark() -> SparkSession:
    from pyspark.sql import SparkSession

    b = (
        SparkSession.builder.appName("sparkrules-kafka-iceberg")
        .config("spark.sql.streaming.checkpointLocation", os.environ["CHECKPOINT_DIR"])
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
    )
    catalog = os.environ.get("ICEBERG_CATALOG", "glue")
    warehouse = os.environ.get("ICEBERG_WAREHOUSE", "")
    if warehouse:
        b = b.config(f"spark.sql.catalog.{catalog}", "org.apache.iceberg.spark.SparkCatalog").config(
            f"spark.sql.catalog.{catalog}.warehouse", warehouse
        )
    return b.getOrCreate()


def _score_batch(df: DataFrame, _batch_id: int) -> None:
    from pyspark.sql import functions as F
    from sparkrules.spark import apply_drl

    drl = _load_drl()
    # Kafka value: JSON object {"amount": 123} — align keys with your DRL fact type `T`.
    fact_schema = "struct<amount:bigint>"
    parsed = df.select(F.from_json(F.col("value").cast("string"), fact_schema).alias("t"))
    scored = apply_drl(parsed, drl, use_v2=True)
    table = os.environ["ICEBERG_OUTPUT_TABLE"]
    # Append rows to Iceberg (catalog must be configured).
    scored.writeTo(table).append()


def main(argv: list[str] | None = None) -> int:
    _ = argv
    os.environ.setdefault("KAFKA_TOPIC", "facts")
    os.environ.setdefault("CHECKPOINT_DIR", "/tmp/sparkrules-ckpt")
    os.environ.setdefault("ICEBERG_OUTPUT_TABLE", "local.db.facts_scored")
    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ["KAFKA_TOPIC"]
    checkpoint = os.environ["CHECKPOINT_DIR"]

    try:
        spark = _build_spark()
    except Exception as e:  # noqa: BLE001 — operator-facing script
        sys.stderr.write(
            json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "hint": "PySpark and Iceberg JARs must be available. Import locally with pip install sparkrules[spark].",
                },
                indent=2,
            )
            + "\n"
        )
        return 1

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap)
        .option("subscribe", topic)
        .option("startingOffsets", os.environ.get("KAFKA_STARTING_OFFSETS", "latest"))
        .option("failOnDataLoss", "false")
        .load()
    )

    def foreach_batch(df: DataFrame, batch_id: int) -> None:
        if df.isEmpty():
            return
        _score_batch(df, batch_id)

    q = raw.writeStream.foreachBatch(foreach_batch).option("checkpointLocation", checkpoint).start()
    q.awaitTermination()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
