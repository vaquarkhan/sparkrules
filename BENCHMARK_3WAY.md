# Three-way benchmark positioning: SparkRules vs Drools vs “Python pack”

**Purpose:** Corrected marketing-grade positioning (not a substitute for reproducible harnesses).  
**Deep dive:** [docs/SPARKRULES_VS_THE_WORLD.md](docs/SPARKRULES_VS_THE_WORLD.md)  
**Harnesses:** [docs/BENCHMARKS.md](docs/BENCHMARKS.md)

---

## What we claim — and what we do not

| Dimension | SparkRules | Drools (PHREAK) | Python rule-engine pack (rule-engine / business-rules) |
|-----------|-------------|-----------------|-----------------------------------------------------------|
| **Single-fact p99** | Mid-pack (Python + compile) | **Best** (JVM, mature JIT) | Slower than SparkRules at 50-rule alpha sharing |
| **Single-machine batch** | Strong in Python tier | **Best** single JVM throughput | Weaker compile amortization |
| **Distributed billions of rows** | **Native** Spark DataFrame + Catalyst | Not a product feature; DIY sharding | Not viable |
| **Lakehouse output** | Iceberg / Delta / Hudi paths | External ETL | External ETL |
| **Same DRL on laptop + cluster** | **Yes** | Laptop = JVM; cluster = custom | Usually laptop only |

**Corrected headline:** SparkRules is not “faster than Drools per core.” It is **the distributed, Python-native, Spark-native rules layer** for lakehouse batch scoring, with honest per-core latency vs JVM engines.

---

## Cost story (illustrative)

Batch-scoring **1B rows/day** with Spark + spot pricing is documented in [docs/SPARKRULES_VS_THE_WORLD.md](docs/SPARKRULES_VS_THE_WORLD.md) §1. Drools cost at 1B rows is not comparable—architecture does not target the same job shape.

---

## When to pick which

- **Drools:** sub-100 µs p99, mature governance, JVM org standard.  
- **SparkRules:** PySpark already owns the data plane; rules as Catalyst-friendly projections (Strategy A).  
- **Lightweight Python libs:** small ruleset, no Spark, no DRL requirement.
