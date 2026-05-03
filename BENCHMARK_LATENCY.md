# Single-fact latency benchmark (SparkRules + peers)

**Methodology:** Same hardware family, single process unless noted; see [docs/SPARKRULES_VS_THE_WORLD.md](docs/SPARKRULES_VS_THE_WORLD.md) §3 for full context and caveats (Python 3.11 vs 3.13, PySpark version).

## 50-rule lending-style pack — p99 order-of-magnitude

| Engine | p99 (order of magnitude) | Notes |
|--------|----------------------------|-------|
| Drools PHREAK | ~20–50 µs | Literature / vendor-class JVM path |
| GoRules Zen | ~100–200 µs | Literature, Go process |
| **SparkRules V2** | **~0.5–0.7 ms** | Measured on Windows reference laptop (see world doc) |
| rule-engine | ~1.5 ms | Measured |
| business-rules | ~1.9 ms | Measured |

## Takeaway

SparkRules targets **compile-once, amortize-on-millions-of-rows** via alpha sharing and optional Spark pushdown—not raw single-fact JVM latency.

## Reproduce locally

```bash
python -m pip install -e ".[test]"
# See tests/perf/ and docs/BENCHMARKS.md for harness entry points.
```

For **Req 18** numeric targets vs measured gap, see [docs/REQUIREMENTS_V2_ENGINE.md](docs/REQUIREMENTS_V2_ENGINE.md) and the Python 3.13 caveat in the world comparison doc.
