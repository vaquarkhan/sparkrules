# Thirteen-engine comparison (side-by-side)

**Legend:** ✅ strong · ⚠️ partial / caveats · ❌ not applicable

| # | Engine | Primary language | DRL-like text rules | Distributed batch (1B+ rows) | Stateful CEP | OSS license | Notes |
|---|--------|------------------|---------------------|-------------------------------|--------------|-------------|-------|
| 1 | **SparkRules** | Python | ✅ DRL subset | ✅ Spark / Catalyst | ❌ | Apache-2.0 | Lakehouse sinks, OPA export, DQ |
| 2 | **Drools / KIE** | Java | ✅ DRL | ❌ (DIY workers) | ✅ | Apache-2.0 | PHREAK, governance gold standard |
| 3 | **GoRules Zen** | Go | ⚠️ JDM / tables | ❌ | ❌ | MIT | Very fast single process |
| 4 | **Camunda Platform** | JVM | ❌ (DMN/BPMN) | ❌ | ⚠️ process | Apache-2.0 | DMN + workflow |
| 5 | **IBM ODM** | JVM / RES | ❌ | ⚠️ RES cluster ($) | ⚠️ | Commercial | Enterprise decision hub |
| 6 | **Apache Flink CEP** | Java/Scala | ❌ | ✅ streaming | 🏆 | Apache-2.0 | Different workload (events) |
| 7 | **python rule-engine** | Python | ⚠️ limited DSL | ❌ | ❌ | BSD | Simple chains |
| 8 | **python business-rules** | Python | ⚠️ | ❌ | ❌ | MIT | Lightweight |
| 9 | **Open L Tablets** | Java | ⚠️ spreadsheets | ❌ | ❌ | Apache-2.0 | Enterprise tables |
| 10 | **Easy Rules** | Java | ⚠️ Java fluent API | ❌ | ❌ | MIT | Minimal engine |
| 11 | **Intellect** | Python | ⚠️ DSL | ❌ | ❌ | BSD | Older maintenance mode |
| 12 | **Open Policy Agent (Rego)** | Rego | ❌ | ⚠️ via sidecars | ❌ | Apache-2.0 | Policy-as-code; SparkRules can export |
| 13 | **Durable Rules (Python)** | Python | ⚠️ | ❌ | ⚠️ embedded | MIT | Forward-chaining variant |

**SparkRules differentiators in this set:** Spark-native DataFrame evaluation, optional SQL pushdown (Strategy A), pandas batch, regulatory helpers (ECOA/GDPR adverse action), OPA export, property-based tests.

For narrative “when to pick which,” see [docs/SPARKRULES_VS_THE_WORLD.md](docs/SPARKRULES_VS_THE_WORLD.md) §6.
