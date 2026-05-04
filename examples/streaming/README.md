# Streaming examples — SparkRules

 Runnable paths for **Kafka / Iceberg production jobs**, **Spark Structured Streaming simulators** (no broker),
**Flink-style per-event** scoring, and **pure-Python** local simulators so you can test DRL without
a cluster.

## Quick test (no JVM, no Kafka)

| File | Command | What it does |
|------|---------|----------------|
| [local_stream_simulator.py](local_stream_simulator.py) | `python local_stream_simulator.py --count 20` | Random facts → `LocalRuleExecutor` |
| [local_stream_simulator.py](local_stream_simulator.py) | `python local_stream_simulator.py --jsonl sample_events.jsonl` | Same, from [sample_events.jsonl](sample_events.jsonl) |
| [flink_style_event_simulator.py](flink_style_event_simulator.py) | `python flink_style_event_simulator.py --demo` | One-at-a-time events (Flink *processElement* style) |

Requires: `pip install sparkrules` (core). Uses shared DRL: [rules/ingress.drl](rules/ingress.drl).

## Spark Structured Streaming (simulated or production)

| File | Command | What it does |
|------|---------|----------------|
| [spark_structured_streaming_rate_simulator.py](spark_structured_streaming_rate_simulator.py) | `pip install 'sparkrules[spark]'` then `python spark_structured_streaming_rate_simulator.py` | **`rate` source** micro-batches + `foreachBatch` + `apply_drl` — no Kafka |
| [kafka_iceberg_structured_streaming.py](kafka_iceberg_structured_streaming.py) | `spark-submit` with Kafka + Iceberg packages | Reference **Kafka → Iceberg** job for operators |

Env hints for the rate simulator: `RATE_ROWS_PER_SECOND`, `STREAM_SECONDS`, `CHECKPOINT_DIR`, `STREAM_TRIGGER`.

## Flink + Kafka (Python sidecar pattern)

Same DRL semantics as streaming ingress rules; production Flink jobs usually call HTTP or a sidecar
instead of embedding Python. See **[../stream/flink-kafka-rules/](../stream/flink-kafka-rules/)** for
`python_sidecar_consumer.py` and **optional** Kafka:

```text
python flink_style_event_simulator.py   # --demo or stdin — no broker
pip install kafka-python
python flink_style_event_simulator.py --kafka   # needs KAFKA_BOOTSTRAP / KAFKA_TOPIC
```

## Spark + Kafka (full pipeline)

Parity job with Parquet sink: **[../stream/spark-kafka-rules/](../stream/spark-kafka-rules/)**
(`spark_kafka_structured_streaming.py` + `rules/ingress.drl`). You can point `SPARKRULES_DRL_PATH`
to **this** folder’s [rules/ingress.drl](rules/ingress.drl) for identical rules.

## Shared rule file

[rules/ingress.drl](rules/ingress.drl) — `high_amount_hold` / `default_ok` on fact type **`T`** with `amount`.
Edit paths or set **`SPARKRULES_DRL_PATH`** to use your own pack.
