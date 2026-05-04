# Flink ↔ SparkRules integration

## Option 1 — Flink Async I/O → SparkRules API

1. **Flink job** consumes `facts` topic (JSON).
2. `RichAsyncFunction` issues HTTP `POST` to `/simulations` or a dedicated **score** microservice wrapping `LocalRuleExecutor`.
3. Results land in a **sink topic** or JDBC.

Use connection pooling, timeouts, and **circuit breakers** — synchronous per-record latency is bound by RTT + Python evaluation.

## Option 2 — PyFlink + LocalRuleExecutor

If your cluster supports **PyFlink**, a **Python map** function can `from sparkrules.executor.local_executor import LocalRuleExecutor` and load **`rules/ingress.drl`**. You still pay Python process overhead; ensure the DRL file is on the task manager classpath or fetched from object storage.

## Option 3 — Flink → Kafka → Spark

Flink does **CEP / windows**; Spark Structured Streaming (this repo’s **`spark-kafka-rules`** folder) does **rules**. Partition by key so ordering matches your policy.

## Governance

Production flows should pin **rule pack versions** (hash / semver) the same way as Spark batch (`PromotionRegistry`, metadata store) — not re-read mutable files on every event unless intentional.
