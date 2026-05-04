"""Kafka → Spark Structured Streaming → SparkRules (DRL from rules/ingress.drl).

Minimal sink: Parquet on local path or S3A. Swap in Iceberg/Delta using the same ``scored`` frame.

Requires: PySpark, spark-sql-kafka, pip install sparkrules[spark]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame, SparkSession

_DRL_CACHE: str | None = None


def _drl_path() -> str:
    env = os.environ.get("SPARKRULES_DRL_PATH", "").strip()
    if env:
        return env
    here = Path(__file__).resolve().parent / "rules" / "ingress.drl"
    return str(here)


def _load_drl() -> str:
    global _DRL_CACHE
    if _DRL_CACHE is not None:
        return _DRL_CACHE
    p = _drl_path()
    if os.path.isfile(p):
        _DRL_CACHE = Path(p).read_text(encoding="utf-8")
        return _DRL_CACHE
    _DRL_CACHE = os.environ.get(
        "SPARKRULES_DRL",
        'rule "fallback" when $t : T ( true ) then result.ok = true; end',
    )
    return _DRL_CACHE


def _build_spark() -> SparkSession:
    from pyspark.sql import SparkSession

    checkpoint = os.environ.get("CHECKPOINT_DIR", "/tmp/sparkrules-ckpt-stream")
    return (
        SparkSession.builder.appName("sparkrules-stream-kafka")
        .config("spark.sql.streaming.checkpointLocation", checkpoint)
        .getOrCreate()
    )


def _score_batch(df: DataFrame, _batch_id: int) -> None:
    from pyspark.sql import functions as F
    from sparkrules.spark import apply_drl

    drl = _load_drl()
    # Kafka value JSON: {"amount": 12345} → struct matches DRL ``T``
    fact_schema = "struct<amount:long>"
    parsed = df.select(F.from_json(F.col("value").cast("string"), fact_schema).alias("t"))
    scored = apply_drl(parsed, drl, use_v2=True)
    out_dir = os.environ.get("STREAM_OUTPUT_PATH", "/tmp/sparkrules-stream-out")
    scored.write.mode("append").format("parquet").save(out_dir)


def main(argv: list[str] | None = None) -> int:
    _ = argv
    os.environ.setdefault("KAFKA_TOPIC", "facts")
    os.environ.setdefault("CHECKPOINT_DIR", "/tmp/sparkrules-ckpt-stream")

    try:
        spark = _build_spark()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "hint": "Install sparkrules[spark]; use Spark 3.5 + matching kafka package.",
                },
                indent=2,
            )
            + "\n"
        )
        return 1

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = os.environ["KAFKA_TOPIC"]
    checkpoint = os.environ["CHECKPOINT_DIR"]

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
