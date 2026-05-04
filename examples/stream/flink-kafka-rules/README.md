# Flink + Kafka + rules (integration patterns)

**Apache SparkRules** is a **Python / PySpark** engine. It does **not** embed into the Flink JVM as a native operator. For Flink pipelines you have three common patterns:

| Pattern | Flow | Trade-offs |
|---------|------|------------|
| **A. Async I/O → REST** | Flink `AsyncFunction` calls **SparkRules HTTP API** (`pip install sparkrules[api]`) with JSON facts | Lowest ops if API already exists; network latency |
| **B. Side-output → Python** | Flink writes keyed JSON to a **side topic**; small **Python consumers** score with `LocalRuleExecutor` | Duplicates compute; good for pilots |
| **C. Hybrid batch** | Flink materializes windows → **Spark batch job** `apply_drl` on landing zone | Strong for heavy scoring bursts |

This folder ships **parity DRL** under `rules/` so the **same policy** can be loaded by the **Spark** path (`examples/stream/spark-kafka-rules/`) or by a **Python** service used from Flink.

## Reference architecture (REST)

1. Deploy SparkRules API (`python -m uvicorn sparkrules.api.app:create_app --factory`).
2. From Flink (Java), `POST /simulations` or your thin **score** route with rule pack ID — or embed **`LocalRuleExecutor`** in a **PyFlink** task (still Python on the cluster).

## Files

| Path | Purpose |
|------|---------|
| `rules/ingress.drl` | Same logical rules as the Spark example (keep in sync manually or via CI) |
| `ARCHITECTURE.md` | Sequence diagram notes for async HTTP integration |

## Minimal Kafka test (Python, no Flink JVM)

For local parity without building a Flink JAR, run the **Spark** example or a plain **kafka-python** consumer calling `LocalRuleExecutor`—see **`python_sidecar_consumer.py`**.
