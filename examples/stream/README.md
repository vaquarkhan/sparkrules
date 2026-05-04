# Stream processing examples (Kafka + rules)

Pair of **standalone folders**—each ships **DRL** under `rules/` and documentation for wiring **Spark** or **Flink** to score facts.

| Folder | Engine | SparkRules path |
|--------|--------|-----------------|
| [spark-kafka-rules/](spark-kafka-rules/) | **Spark** Structured Streaming + PySpark | Native `sparkrules.spark.apply_drl` |
| [flink-kafka-rules/](flink-kafka-rules/) | **Apache Flink** (Java/Scala) | **Not** JVM-native; integrate via **HTTP** (`SreClient`) or **Kafka → Python** sidecar—see README |

Also see **[../streaming/README.md](../streaming/README.md)** for **local / rate-source simulators** (no Kafka),
Flink-style per-event scoring, and the **Kafka → Iceberg** reference job.
