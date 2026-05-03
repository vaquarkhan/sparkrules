# Optimized benchmark (prototype results)

**Status:** This file captures **prototype / harness-level** results and pointers—not a fixed “leaderboard” checked into CI.

## Where numbers live

| Artifact | Purpose |
|----------|---------|
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Harness APIs, lakehouse evidence expectations |
| [docs/SPARKRULES_VS_THE_WORLD.md](docs/SPARKRULES_VS_THE_WORLD.md) | Measured Python engines + literature JVM rows |
| [BENCHMARK_LATENCY.md](BENCHMARK_LATENCY.md) | Single-fact p99 summary |
| [BENCHMARK_3WAY.md](BENCHMARK_3WAY.md) | SparkRules vs Drools vs Python pack |

## In-repo harnesses

- `sparkrules.runtime.perf.run_perf_harness` — wall clock + rows/sec for a callable.  
- `sparkrules.runtime.perf.scale_evidence` — structured scaling estimate for docs/SLO.  
- `pytest -m perf` — opt-in perf tests (`tests/perf/`).

## Distributed projections (Strategy A)

Projected 200-executor wall-clock numbers in the world comparison doc assume **shuffle-free** Catalyst projections and conservative parallel efficiency. **Real cluster** runs should file evidence under your org’s perf process (see [docs/BENCHMARKS.md](docs/BENCHMARKS.md) “production evidence”).

## Next measurements (suggested)

1. Spark 3.5 on Java 17, `local[4]` vs 8-executor fixed dataset (Parquet).  
2. Same rule pack on `LocalRuleExecutor` for parity delta.  
3. Record Spark UI stage time + driver heap with 10k-rule pack (memory bound stress).
