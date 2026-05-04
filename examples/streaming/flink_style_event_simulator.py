"""Flink-style streaming: **one event at a time** (like a Flink processElement) with LocalRuleExecutor.

Parallels the Python sidecar in ``examples/stream/flink-kafka-rules/`` — but **no Kafka** by default,
so you can test rules in CI or on a laptop.

  # Built-in demo: 15 events with random amounts
  python flink_style_event_simulator.py --demo

  # Pipeline-friendly: NDJSON facts, one per line (stdin)
  echo '{"t":{"amount":500}}' | python flink_style_event_simulator.py

  # With Kafka (optional): pip install kafka-python
  export KAFKA_BOOTSTRAP=localhost:9092
  python flink_style_event_simulator.py --kafka
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

_DRL = Path(__file__).resolve().parent / "rules" / "ingress.drl"


def _load_drl(custom: str | None) -> str:
    if custom and Path(custom).is_file():
        return Path(custom).read_text(encoding="utf-8")
    p = (os.environ.get("SPARKRULES_DRL_PATH", "") or "").strip()
    if p and Path(p).is_file():
        return Path(p).read_text(encoding="utf-8")
    return _DRL.read_text(encoding="utf-8")


def _score_one(exe, fact: dict[str, object]) -> dict[str, object]:
    r = exe.score(fact)
    return {
        "fired": r.fired_any,
        "merged_actions": r.merged_actions,
    }


def _run_stdin(exe) -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        fact = raw if "t" in raw else {"t": raw}
        out = _score_one(exe, fact)
        print(json.dumps({"source": "stdin", **out}))
    return 0


def _run_demo(exe, count: int, seed: int, delay_ms: int) -> int:
    rnd = random.Random(seed)
    for i in range(count):
        fact = {"t": {"amount": rnd.randint(0, 25000)}}
        out = _score_one(exe, fact)
        print(json.dumps({"seq": i, **out}))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
    return 0


def _run_kafka(exe, bootstrap: str, topic: str) -> int:
    from kafka import KafkaConsumer  # type: ignore[import-untyped]

    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=[bootstrap],
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        auto_offset_reset="latest",
        consumer_timeout_ms=5000,
    )
    try:
        for msg in consumer:
            fact = {"t": msg.value} if isinstance(msg.value, dict) else {"t": {}}
            out = _score_one(exe, fact)
            print(
                json.dumps(
                    {"offset": msg.offset, **out},
                ),
            )
    finally:
        consumer.close()
    return 0


def main() -> int:
    from sparkrules.executor.local_executor import LocalRuleExecutor

    p = argparse.ArgumentParser(description="Flink-style per-event rule scoring.")
    p.add_argument("--demo", action="store_true", help="Generate synthetic events (no stdin).")
    p.add_argument("--count", type=int, default=15)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--delay-ms", type=int, default=0, help="Sleep between demo events.")
    p.add_argument("--kafka", action="store_true", help="Consume from Kafka (needs kafka-python).")
    p.add_argument("--drl", type=str, default="", help="Path to DRL file.")
    args = p.parse_args()

    drl = _load_drl(args.drl or None)
    exe = LocalRuleExecutor.from_drl(drl)

    if args.kafka:
        return _run_kafka(
            exe,
            os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092"),
            os.environ.get("KAFKA_TOPIC", "facts"),
        )
    if args.demo or sys.stdin.isatty():
        return _run_demo(exe, max(1, args.count), args.seed, args.delay_ms)
    return _run_stdin(exe)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(130)
