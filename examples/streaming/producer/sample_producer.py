#!/usr/bin/env python3
"""
Sample Kafka producer for SparkRules loan-underwriting streaming demo.

Author: Ram Ghadiyaram

Generates realistic loan application facts and publishes them as JSON
to the configured Kafka topic.

Usage:
    pip install kafka-python
    python sample_producer.py --count 50 --bootstrap localhost:9092 --topic facts
"""

from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

REGIONS = ["US", "CA", "UK", "DE", "XX", "YY", "ZZ", "IN", "AU"]
PRODUCTS = ["personal", "auto", "mortgage", "business", "student"]


def make_fact() -> dict[str, Any]:
    """Create one realistic loan application fact. No external deps."""
    amount = random.choice(
        [5_000, 12_000, 25_000, 40_000, 55_000, 80_000, 120_000, 250_000]
    )
    credit_score = random.randint(500, 850)
    return {
        "application_id": str(uuid.uuid4()),
        "amount": amount,
        "credit_score": credit_score,
        "region": random.choice(REGIONS),
        "product": random.choice(PRODUCTS),
        "applicant_age": random.randint(21, 70),
        "event_ts": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="SparkRules sample Kafka producer")
    parser.add_argument("--bootstrap", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="facts", help="Kafka topic")
    parser.add_argument("--count", type=int, default=30, help="Number of messages to send")
    parser.add_argument("--interval", type=float, default=0.3, help="Seconds between messages")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    try:
        from kafka import KafkaProducer
    except ImportError as e:
        raise SystemExit(
            "kafka-python is required to publish: pip install kafka-python\n" + str(e)
        ) from e

    if args.seed is not None:
        random.seed(args.seed)

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=3,
    )

    print(f"Publishing {args.count} facts to {args.topic} @ {args.bootstrap}")
    for i in range(args.count):
        fact = make_fact()
        key = fact["application_id"]
        future = producer.send(args.topic, key=key, value=fact)
        record = future.get(timeout=10)
        print(
            f"[{i+1:03d}] {fact['application_id'][:8]}… "
            f"amount={fact['amount']:,} score={fact['credit_score']} "
            f"region={fact['region']} → partition={record.partition} offset={record.offset}"
        )
        time.sleep(args.interval)

    producer.flush()
    producer.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
