"""Small Kafka consumer scoring with LocalRuleExecutor (optional Flink parity / dev).

Not for high-throughput production; use Spark streaming or a pooled REST service instead.

  pip install kafka-python sparkrules
  export KAFKA_BOOTSTRAP=localhost:9092
  export KAFKA_TOPIC=facts
  python python_sidecar_consumer.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from kafka import KafkaConsumer  # type: ignore[import-untyped]

_DRL_TEXT: str | None = None


def _load_drl() -> str:
    global _DRL_TEXT
    if _DRL_TEXT is not None:
        return _DRL_TEXT
    p = Path(__file__).resolve().parent / "rules" / "ingress.drl"
    _DRL_TEXT = p.read_text(encoding="utf-8")
    return _DRL_TEXT


def main() -> None:
    from sparkrules.executor.local_executor import LocalRuleExecutor

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
    topic = os.environ.get("KAFKA_TOPIC", "facts")
    drl = _load_drl()
    executor = LocalRuleExecutor.from_drl(drl)

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=[bootstrap],
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        auto_offset_reset="latest",
        consumer_timeout_ms=5000,
    )
    for msg in consumer:
        fact = {"t": msg.value}
        r = executor.score(fact)
        print(json.dumps({"offset": msg.offset, "fired": r.fired_any, "actions": r.merged_actions}))
    consumer.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
