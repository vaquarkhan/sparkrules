"""Spark Structured Streaming **without Kafka**: built-in `rate` source + foreachBatch + apply_drl.

Models micro-batches the same way as a Kafka stream; ideal for laptop testing before brokers.

  pip install 'sparkrules[spark]'
  python spark_structured_streaming_rate_simulator.py

Env:
  RATE_ROWS_PER_SECOND (default 3)
  STREAM_SECONDS (default 12) — run duration, then stop the query
  CHECKPOINT_DIR (default tempdir subfolder)
  STREAM_TRIGGER (default \"2 seconds\")
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

_DRL_PATH = Path(__file__).resolve().parent / "rules" / "ingress.drl"


def _load_drl() -> str:
    p = (os.environ.get("SPARKRULES_DRL_PATH", "") or "").strip()
    if p and Path(p).is_file():
        return Path(p).read_text(encoding="utf-8")
    return _DRL_PATH.read_text(encoding="utf-8")


def _build_spark():
    from pyspark.sql import SparkSession

    return (
        SparkSession.builder.appName("sparkrules-rate-simulator")
        .master(os.environ.get("SPARK_MASTER", "local[2]"))
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def _foreach_batch(drl: str):
    from pyspark.sql import functions as F
    from sparkrules.spark import apply_drl

    def _go(df: DataFrame, batch_id: int) -> None:
        parsed = df.select(F.struct(F.col("value").cast("long").alias("amount")).alias("t"))
        scored = apply_drl(parsed, drl, use_v2=True)
        n = scored.count()
        print(
            json.dumps({"batch_id": batch_id, "rows": n, "sink": "show"}),
            file=sys.stderr,
        )
        scored.show(truncate=False)

    return _go


def main() -> int:
    rows_per_sec = float(os.environ.get("RATE_ROWS_PER_SECOND", "3"))
    stream_seconds = float(os.environ.get("STREAM_SECONDS", "12"))
    ck_root = os.environ.get("CHECKPOINT_DIR", tempfile.mkdtemp(prefix="sparkrules-rate-"))
    ckpt = os.path.join(ck_root, "checkpoint")
    trigger = os.environ.get("STREAM_TRIGGER", "2 seconds")

    try:
        spark = _build_spark()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(
            json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "hint": "pip install 'sparkrules[spark]' and ensure Java is available for PySpark.",
                },
                indent=2,
            )
            + "\n"
        )
        return 1

    drl = _load_drl()
    raw = spark.readStream.format("rate").option("rowsPerSecond", rows_per_sec).load()
    q = (
        raw.writeStream.option("checkpointLocation", ckpt)
        .foreachBatch(_foreach_batch(drl))
        .trigger(processingTime=trigger)
        .start()
    )
    timeout_ms = int(stream_seconds * 1000)
    q.awaitTermination(timeout_ms)
    q.stop()
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
