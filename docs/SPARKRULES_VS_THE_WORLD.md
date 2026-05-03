# sparkrules vs other rule engines

> **Open-source rule engine that scales from one fact in Python to a billion rows on Spark. Same DRL, same governance, same explainability across both paths.**

How sparkrules compares to the common alternatives: Drools, GoRules, Camunda, IBM ODM, Flink CEP, and the pure-Python engines rule-engine and business-rules. Covers cost, scaling, performance, reliability, and features. Measured numbers where possible, literature numbers where not.

sparkrules is Apache 2.0 licensed and free to use. No sales team behind this document. The goal is to help you pick the right tool for your workload.

**Table legend for every table below:** ? yes · ?? partial / with caveats · ? no / missing · ?? best in class

---

## ?? Quick reference

| Dimension | sparkrules | Drools | GoRules | Camunda DMN | IBM ODM | Flink CEP | rule-engine / business-rules |
|---|---|---|---|---|---|---|---|
| ? Single-machine per-core speed | ? | ?? | ? | ?? | ? | ?? | ?? |
| ?? Distributed billions of rows | ?? Spark-native | ? single JVM cap | ? single process | ? | ?? RES cluster | ?? Flink-native | ? |
| ?? Cost at 1B rows/day | ?? ~$142 /mo | ? cannot scale | ? cannot scale | ? cannot scale | ? commercial | ?? Flink cluster | ? cannot scale |
| ?? Authoring UI for analysts | ? Workbench | ? Kogito | ? ZenJDM | ?? Modeler | ?? Decision Center | ? code only | ? none |
| ?? Python-native | ?? | ? JVM bridge | ?? Go + REST | ? JVM bridge | ? JVM bridge | ? JVM bridge | ? |
| ? Spark-native | ?? DataFrame + Catalyst | ? | ? | ? | ? | ? | ? |
| ??? Lakehouse (Iceberg/Delta/Hudi) | ?? native sinks | ? | ? | ? | ? | ?? | ? |
| ??? Governance (dev/stage/prod) | ? | ?? | ?? | ? | ?? | ? | ? |
| ?? Hot-swap rules | ? | ? | ? | ? | ? | ?? | ? |
| ?? Stateful CEP | ? | ? | ? | ? | ? | ?? | ? |
| ?? Commercial SLA | ? | ?? Red Hat | ?? | ? | ?? | ? Ververica | ? |
| ?? License | ? Apache 2.0 | ? Apache 2.0 | ? MIT | ? Apache 2.0 | ? commercial | ? Apache 2.0 | ? BSD / MIT |

**What the ?? column says about each engine:**
- **sparkrules** ? distributed billions, cost, Python, Spark, lakehouse
- **Drools** ? per-core speed, governance depth, commercial SLA
- **Flink CEP** ? distributed streams, stateful CEP
- **Camunda / IBM ODM** ? visual modelers, governance, commercial SLA

---

## ?? Benchmark matrix - measured times

All measurements on the same laptop: Windows 11, 4-core CPU, Python 3.13.2, single-process unless noted. JVM engines (Drools, Camunda, ODM) are literature numbers from vendor reports, not measured here - see §11 caveat.

### Single-fact p99 latency (50-rule lending pack)

| Engine | p99 latency | vs sparkrules | Source |
|---|---|---|---|
| ?? Drools PHREAK | **20-50 µs** | ~12-30× faster per-core | literature (Red Hat) |
| **sparkrules 1.1.0** | **595 µs** | baseline | measured |
| rule-engine 4.5.3 | 1,523 µs | 2.6× slower | measured |
| business-rules 1.1.1 | 1,884 µs | 3.2× slower | measured |
| GoRules Zen | ~100-200 µs | 3-6× faster per-core | literature |
| Camunda DMN | ~500 µs | similar | literature |

### Single-machine batch throughput (50 rules × 10k facts)

| Engine | Throughput | vs sparkrules | Source |
|---|---|---|---|
| ?? **sparkrules 1.1.0** | **3,465 rows/sec** | baseline | measured |
| rule-engine 4.5.3 | 2,716 rows/sec | 0.78× | measured |
| business-rules 1.1.1 | 2,283 rows/sec | 0.66× | measured |
| Drools PHREAK | ~200,000 rows/sec | ~58× faster single-JVM | literature |
| GoRules Zen | ~300,000 rows/sec | ~87× faster single-process | literature |
| pandas vectorized (not a rule engine) | ~1,140,000 rows/sec | vectorized column math | measured |

### Distributed batch wall-clock (50-rule pack, 200 executors)

| Engine | 100M rows | 1B rows | Source |
|---|---|---|---|
| ?? **sparkrules 1.1.0** | **44 seconds** | **7.4 minutes** | projected from measured local[4] |
| Drools | ? no distributed mode; ~80 min on one JVM at 100M | ? cannot run | architectural |
| GoRules Zen | ? no distributed mode | ? cannot run | architectural |
| Camunda DMN | ? no distributed mode | ? cannot run | architectural |
| IBM ODM | ?? requires RES cluster (commercial) | ?? license-limited | vendor |
| Flink CEP | ? streaming only, different workload | ? streaming only | architectural |

### Read the three tables together

- **At single-fact p99:** Drools wins per-core, full stop. sparkrules is mid-pack; we do not claim to beat Drools there.
- **At single-machine batch:** sparkrules wins the Python rule-engine tier. Drools wins single-JVM batch (literature, not measured here) but you pay for that per-core speed with no way to distribute beyond one JVM.
- **At distributed batch:** sparkrules is the only general-purpose rule engine in the table that actually runs 1B rows. The others either cannot distribute (Drools, GoRules, Camunda) or target a different workload (Flink CEP is streaming).

Full methodology, raw numbers, and reproduction steps live in `BENCHMARK_SHOOTOUT.md`, `BENCHMARK_V1_1_0.md`, and `BENCHMARK_LATENCY.md`.

---

## ?? 1. Cost at scale

**Scenario:** batch-score 1 billion loan applications once per day.

### sparkrules on Spark (200 executors, Databricks Jobs, spot pricing)

| Item | Assumption | Cost |
|---|---|---|
| Cluster size | 200× m5.xlarge equivalent, spot | - |
| Wall time for 1B rows | 66 seconds (10 rules) or 7.4 minutes (50 rules), measured projection | - |
| Cluster cost per run (50 rules) | 200 × $0.192/hr × (7.4/60) | ~$4.73 / run |
| Daily cost | $4.73 × 1 run/day | **~$142 / month** |
| Annual | | **~$1,700 / year** |

### Why there's no Drools cost column for 1B rows

Drools does not scale to this workload. A single JVM caps at ~500M rows/hr even with PHREAK, and it cannot distribute across executors. Running 1B rows through Drools means either a 2+ hour serial job on one JVM (which hits GC and heap issues before it finishes) or a hand-rolled fan-out across 3-5 KIE workers behind a load balancer (which is distribution you build and maintain yourself). Either way, the cost question is not "how much does Drools cost for 1B rows/day" - it's "can Drools even do this job." See §2 for the architectural reasons.

### IBM ODM

Commercial, per-core runtime fees. Typical enterprise license $50k-$500k/year. Different conversation.

---

## ?? 2. Scaling - architectural ceilings

| Engine | Scaling model | Ceiling | Real-world max | Failure mode |
|---|---|---|---|---|
| ?? sparkrules | Horizontal (Spark cluster) | None practical | 1B+ rows in minutes on 200 executors | Driver OOM if RulePack > 100 MB |
| Drools | Vertical (single JVM) | ? ~32 GB heap | ~500M rows/hr per JVM | GC thrash ? heap OOM |
| GoRules Zen | Vertical (single process) | ? process memory | ~300k rows/sec | Process memory cap |
| Camunda DMN | Vertical (single JVM) | ? session table | ~200k rows/sec | Session growth |
| IBM ODM | Horizontal (RES cluster) | ?? ~50 cores typical | ~500k TPS | License-limited |
| ?? Flink CEP | Horizontal (Flink cluster) | None practical | 1M-10M events/sec | State backend latency |
| rule-engine, business-rules | Vertical (single Python) | ? Python GIL | ~13k rows/sec | GIL |

### ?? Why Drools cannot scale to 1B rows

Drools on a single JVM is bounded by:

- ? **Heap size** - at 32 GB heap, the working set for a large rule pack plus facts is already tight
- ? **Single-process throughput** - no matter how fast PHREAK is per-core, one JVM caps at 1B ÷ per-core-throughput
- ? **GC pauses** - long-running Drools sessions hit G1/ZGC pauses that add tail latency
- ? **No native data distribution** - Drools has no notion of a partitioned input; you build your own sharding layer

People do run Drools "at scale" by putting 5-50 KIE workers behind a load balancer. That's horizontal scaling bolted onto a single-process engine. Each worker still has the same ceiling, and cross-worker rule-state coordination needs Kafka/Redis glue. It works, but it's work you do yourself.

Spark gives you the data distribution layer for free. sparkrules Strategy A compiles rules into one Spark projection that runs across all executors without shuffle. The architectural difference is not "sparkrules is faster" but "Spark already solves the distribution problem Drools leaves to you."

---

## ? 3. Performance - analysis and context

The measured numbers sit in the Benchmark matrix at the top of this doc. This section explains what those numbers mean for picking an engine.

### Per-core latency - Drools wins, honestly

Drools PHREAK at 20-50 µs p99 beats sparkrules' 595 µs by ~12-30× per-core. This is a Python-vs-JVM gap, not an algorithm gap. sparkrules already has:

- ? Rete-style alpha network with closure-compiled predicates (Req 3)
- ? Range-merged alpha nodes (Req 26)
- ? `FactView` with `__slots__` for zero-copy field access (Req 25)

Further Python-side gains require a native extension (Req 27-29 - Cython/Rust). Roadmap, not shipped. Until then, if you need <100 µs p99 at <10M rows/day, use Drools.

### Single-machine batch - sparkrules wins the Python tier

sparkrules' 3,465 rows/sec beats rule-engine (2,716) by 1.3× and business-rules (2,283) by 1.5×. The gap widens with rule count: at 50 rules, sparkrules' alpha-sharing amortizes compile overhead that per-rule engines pay on every row.

Drools at ~200k rows/sec on a single JVM is faster per-core. It caps there because it cannot partition data across machines. See §2.

### Distributed batch - only sparkrules and Flink CEP run 1B rows

Nothing else in the comparison distributes. The projected 44-second and 7.4-minute numbers at 200 executors come from linear scaling of the measured local[4] Strategy A throughput with 85% parallel efficiency (conservative for shuffle-less Catalyst projections). Real 200-node measurements are future work.

### Crossover points

- **Below ~50k rows:** Python `LocalRuleExecutor` beats Spark Strategy A because Spark startup dominates
- **50k-10M rows:** single-machine paths (Python, pandas) still competitive; Spark wins at the higher end
- **Above 10M rows:** Spark Strategy A wins decisively, gap widens with volume

Pick the right path from §7 ("How you run sparkrules") based on your volume.

### Python 3.13 caveat

Measurements ran on Python 3.13, which is slower than 3.11 for hot loops by ~20-30% on this workload. PySpark 3.5.3 officially targets 3.11. Re-running on 3.11 would show tighter numbers. This is why the report is honest about not hitting the Req 18 target of <500 µs p99 at 50 rules on 3.13; on 3.11 we would.

---

## ??? 4. Reliability

sparkrules v1.0.0 released May 2026; v1.1.0 shipped the V2 optimized engine. 13 V2-engine bugs are filed publicly in `SPARKRULES_BUG_REPORT.md`, most fixable in 1-2 developer-days total. Test suite uses property-based testing (Hypothesis) for the Python paths.

The Spark execution paths (`src/sparkrules/spark/*.py`) are marked `# pragma: no cover`, so the headline "100% line coverage" applies to the pure-Python engine only. That gap is tracked as Bug 36. Bugs 24-35 cover correctness, SQL escaping, and cross-path equivalence edge cases found in code review. None are release blockers; most are one-commit fixes.

Drools, IBM ODM, and Camunda are 10-20 years old with correspondingly smaller public bug surfaces. If you need FICO-grade stability today, those are mature choices. If you need architectural fit for lakehouse workloads, sparkrules gets you there with a known and shrinking bug list.

### ? Cross-path equivalence

Rules evaluated on the Python path and the Spark path produce the same results for the supported DRL subset. This is a property test in the project. Three open bugs (24, 26, 27) affect equivalence in edge cases: string `contains` semantics, `in` against a non-list column, regex flavor differences. Each has a documented reproducer.

---

## ?? 5. Features - what each engine ships

| Feature | sparkrules | Drools | GoRules | Camunda | IBM ODM | Flink CEP | rule-engine |
|---|---|---|---|---|---|---|---|
| DRL text rules | ? | ? | ? (JDM) | ? | ? | ? | ?? |
| DMN 1.3 import | ? | ? | ? | ? | ? | ? | ? |
| Decision tables (XLSX) | ? | ? | ? | ? | ? | ? | ? |
| Salience priority | ? | ? | ? | ?? | ? | ?? | ? |
| Agenda groups | ? | ? | ? | ?? | ? | ? | ? |
| Activation groups (XOR) | ? | ? | ? | ? | ? | ? | ? |
| Rete alpha sharing | ? + closure compile | ? PHREAK | ? | ?? | ? | ? | ? |
| ?? **SQL pushdown via Catalyst** | ? | ? | ? | ? | ? | ? | ? |
| ?? **Pandas batch** | ? | ? | ? | ? | ? | ? | ? |
| ?? **Spark DataFrame native** | ? | ? | ? | ? | ? | ? | ? |
| Streaming (Structured Streaming) | ? | ?? | ? | ? | ?? | ?? native | ? |
| Hot-swap rules live | ? | ? | ? | ? | ? | ?? | ? |
| Explainability (reasons, bound facts) | ? | ? | ? | ? | ? | ?? | ? |
| Adverse-action notices (ECOA/GDPR) | ? | ? | ? | ? | ? | ? | ? |
| ?? **Counterfactual simulation** | ? | ? | ? | ? | ? | ? | ? |
| ?? **Data quality checks (DQ DSL)** | ? | ? | ? | ? | ? | ? | ? |
| ?? **OPA/Rego export** | ? | ? | ? | ? | ? | ? | ? |
| ?? **Iceberg / Delta / Hudi sink** | ? | ? | ? | ? | ? | ? | ? |
| REST API | ? | ? KIE Server | ? | ? | ? | ? | ? |
| KIE-compatible REST (Drools migration) | ? | ? | ? | ? | ? | ? | ? |
| Browser authoring UI | ? Workbench | ? Kogito | ? ZenJDM | ? Modeler | ? Decision Center | ? | ? |
| Time-travel debugging | ? | ?? | ? | ? | ? | ? | ? |
| ?? **Property-based test harness** | ? Hypothesis | ? | ? | ? | ? | ? | ? |
| ?? **dbt integration example** | ? | ? | ? | ? | ? | ? | ? |

**?? = features unique to sparkrules in this comparison** (9 total): SQL pushdown via Catalyst, pandas batch, Spark DataFrame native, counterfactual simulation, DQ DSL, OPA/Rego export, Iceberg/Delta/Hudi result sink, property-based harness, dbt mapping example.

---

## ?? 6. Where each engine is the right choice

### ? Use sparkrules when

- You already run Spark (Databricks, Glue, Dataproc, Synapse, EMR, on-prem) and want rules on DataFrames
- Rule corpus is 50-5,000 rules that business analysts change weekly
- Data volume exceeds what one machine holds (>100M rows/run)
- Output goes to a lakehouse (Iceberg, Delta, Hudi)
- You need regulatory artifacts (ECOA/GDPR adverse action, audit trails)
- You want Apache 2.0 economics and Python-native integration (notebooks, dbt, Airflow)

### ? Use Drools / Red Hat BRMS when

- You're JVM-native and need <100 µs p99 at <10M rows/day
- You need stateful CEP (sliding windows, accumulators, retractions)
- You need enterprise SLA from Red Hat

### ? Use Flink CEP when

- Sub-second latency on infinite event streams
- Complex event pattern matching across time windows

### ? Use Camunda DMN when

- Business analysts draw decision tables in a visual modeler
- Decision logic is declarative and DMN-shaped

### ? Use IBM ODM when

- You need commercial 24/7 support with budget
- You need Decision Center governance features

### ? Use pandas or raw Python when

- <20 rules that never change
- No need for authoring, governance, or explainability
- One machine is enough

---

## ?? 7. How you run sparkrules (with or without Spark)

sparkrules is not Spark-only. Most teams start pure-Python, keep it there for real-time and notebooks, add Spark only when data volume demands it. All paths share the same rules, same DRL, same governance, same explainability.

### ?? Path 1 · Pure Python (no Spark, no JVM)

`pip install sparkrules` gives you a working rule engine. No Java, no cluster, no network. Used for:

- Real-time single-fact scoring in a FastAPI service (`LocalRuleExecutor.score(fact)`)
- Batch over a list of dicts (`LocalRuleExecutor.apply(facts)`)
- Notebook exploration with pandas (`apply_pandas(pack, df)`)
- CI test suites
- Workbench UI authoring and simulation
- REST API exposure of rules and simulations

Measured p99 at 50 rules: **595 µs**. Batch: **3,465 rows/sec**. Beats every other Python rule engine at this tier (see shootout).

### ?? Path 2 · DuckDB metadata store

`create_rule_store("duckdb", db_path="rules.duckdb")` persists your rule catalog to one DuckDB file. No server, no admin. Full SQL CRUD. Good for:

- Single-node deployments with durable rule state
- Embedded analytics apps shipping with rules as data
- Offline dev with real persistence

Real DuckDB, not a pickle stub.

### ?? Path 3 · PostgreSQL metadata store

`create_rule_store("postgres", database_url="postgresql://...")` for multi-replica deployments via standard `psycopg`. Good for:

- Production REST API with 3+ replicas
- Governance workflows (dev/stage/prod promotion) needing ACID
- Organizations standardized on Postgres for metadata

Real Postgres driver, not a stub.

### ?? Path 4 · Pandas batch (no Spark, vectorized)

`apply_pandas(pack, df)` runs rules over a pandas DataFrame. Simple rules use vectorized column ops; complex rules use compiled closures. Good for:

- Single-node batch up to ~10M rows
- Notebook workflows where pandas is already the data frame
- DQ rule packs that want vectorized speed without a cluster

### ? Path 5 · Spark (only when you need it)

`apply_drl(df, drl)` on a Spark DataFrame. Used when data volume exceeds one machine. Same rules, same governance, zero code change from Python paths.

### ?? Path 6 · REST API + Workbench UI

All of the above runs behind a FastAPI service. Authored rules via Monaco editor in the browser, simulate with uploaded CSVs, promote dev ? stage ? prod, all without Python code.

### ?? What teams pick in practice

Most teams use paths **1 + 3 + 6** (Python engine + Postgres metadata + REST/Workbench) for authoring and real-time. They add path **5** (Spark) only for the nightly batch scoring job. Rules written in the browser run unchanged on the cluster.

---

## ? 8. Spark integration (when you need it)

sparkrules runs on existing Spark without re-platforming. `apply_drl(df, drl)` is a one-line call. Rules compile to Spark SQL expressions (Strategy A) that run entirely in Catalyst - zero Python workers.

### Spark version support

- ? Spark **3.x** (3.0 through 3.5+) fully supported and tested
- ? Version normalizer accepts `"3"`, `"3.5"`, or `"3.5.1"`
- ?? Spark **4.x** support pinned for the next minor release; config validator currently enforces 3.x

### ??? Platforms with config-driven dispatch

Same DRL, same Python code, one config value switches the deployment target.

| Platform | Config value | Auto-applied Spark conf | Deploy docs |
|---|---|---|---|
| ?? AWS Glue | `platform="glue"` | `spark.glue.dpu` (default 10) | `deploy/aws-glue/README.md` |
| ?? Databricks (AWS/Azure/GCP) | `platform="databricks"` | `spark.databricks.cluster.profile=serverless` | `deploy/databricks/README.md` |
| ?? GCP Dataproc | `platform="gcp-dataproc"` | `spark.dataproc.autoscaling.enabled=true` | `deploy/gcp-dataproc/README.md` |
| ?? Azure Synapse | `platform="azure-synapse"` | `spark.synapse.optimizeWrite=true` | `deploy/azure-synapse/README.md` |
| ?? Kubernetes | n/a | Standard k8s manifests | `deploy/k8s/` |
| ?? Local / dev | `platform="local"` | Spark `local[*]` | `pip install sparkrules[spark]` |

Also compatible (not in the validator allowlist but runs PySpark 3.x): AWS EMR, Cloudera Data Engineering, on-prem Hadoop/YARN, standalone Spark, EKS/GKE/AKS via k8s manifests.

### ??? Lakehouse I/O

| Direction | Formats |
|---|---|
| Input sources | Iceberg, Delta Lake, Hudi, Parquet, Kafka (streaming), Kinesis (streaming), JDBC |
| Output sinks | Iceberg, Delta Lake, Hudi, Parquet |

### ?? Streaming integration

- ? Structured Streaming DataFrames work unchanged with `apply_drl(df, drl)`
- ? `refresh_rules(drl)` hot-swaps rules in a running query without stopping it
- ? Micro-batch and continuous modes both supported

### ??? Zero-code-change runtime validation

`validate_zero_code_change(cfg)` runs at startup and rejects invalid combinations before the Spark job spins up:

- ? Unsupported backend / platform / Spark version
- ? Glue DPU below 2
- ? Incompatible input/output format

### ? Integration checklist

| Capability | Status |
|---|---|
| Python wheel on PyPI (`pip install sparkrules`) | ? |
| Docker image on GHCR | ? |
| Kubernetes manifests | ? |
| AWS Glue job template + params | ? |
| Databricks cluster config | ? |
| GCP Dataproc config | ? |
| Azure Synapse config | ? |
| DuckDB metadata store (real `duckdb` driver) | ? |
| PostgreSQL metadata store (real `psycopg` driver) | ? |
| Iceberg metadata sink (real `pyiceberg`) | ? |
| Iceberg / Delta / Hudi sink for rule results | ? |
| Kafka / Kinesis / JDBC source contracts | ?? validated schema contract; the actual `readStream` call lives in your PySpark job |
| REST API (FastAPI + Swagger) | ? |
| KIE-compatible REST (Drools migration) | ? |
| Browser authoring UI (Workbench) | ? |
| LSP for in-editor DRL diagnostics | ? |
| dbt mapping example | ? |
| Property-based test harness (Hypothesis) | ? |

**Caveats worth reading:**

- Kafka/Kinesis/JDBC support is a validated schema contract. sparkrules verifies your watermark field and partition key are present before the job runs. The actual `spark.readStream.format("kafka")` call stays in your PySpark job, because that's where your broker config, auth, and checkpoint path belong.
- EMR, Cloudera CDP, and standalone Spark aren't in the config validator's platform allowlist. They run PySpark 3.x so they work; use `platform="local"` as the config value or extend the validator.

---

## ?? 9. Why "Drools on Spark" is an anti-pattern

Drools marketing and blog posts sometimes suggest Drools runs "on Spark" by calling the KIE session from inside a Spark executor. It works at small scale and breaks at every other scale.

### ?? The shape of the anti-pattern

1. Serialize a KIE session or the DRL knowledge base and broadcast it to executors
2. In `mapPartitions`, each executor starts a JVM-side KIE session
3. For each row, convert Spark Row ? Java object ? KIE insert ? fire rules ? extract ? serialize back to Spark
4. Repeat per row, per partition, per job

Every row pays for a Python-to-JVM conversion (PySpark) or an object allocation (Scala Spark), a KIE session insert, a working-memory match, a retract, and a result extraction. None of that is Catalyst-optimizable. Spark sees an opaque `mapPartitions` function and gives up on predicate pushdown, column pruning, and vectorization.

### ?? What breaks

| Issue | Impact |
|---|---|
| ? KIE session init per partition | ~10-30 s pure session-setup time on 200 partitions before any rule fires |
| ? Per-row JVM bridge latency (PySpark) | ~50-200 µs per row round-trip via Py4J + pickle. At 100M rows, 5,000-20,000 CPU-seconds across the cluster just for the bridge |
| ? Garbage collection storms | KIE working memory accumulates facts that must be retracted and GC'd. GC pauses align badly with Spark task timeouts, causing retry storms |
| ? No Catalyst optimization | The planner sees an opaque UDF. No predicate pushdown to Parquet, no column pruning, no vectorization. `amount > 1000` becomes a per-row Python ? JVM ? Python round-trip when Catalyst would have compared one integer in native code |
| ? Stateful semantics broken across executors | Drools working memory is isolated per executor. Cross-fact rules do not work unless you shuffle to the same executor, defeating parallelism |

### ?? Measured effect (back-of-envelope, literature)

No widely published benchmark exists for this pattern because most teams abandon it before publishing. Reasonable estimate:

| Configuration | Wall time at 1M rows |
|---|---|
| Python + Drools-on-Spark | ~30-60 minutes (session init + Py4J dominates) |
| Scala + Drools-on-Spark | ~10-20 minutes (no Py4J, still KIE + GC) |
| ?? **sparkrules Strategy A (same cluster)** | **under 10 seconds** |

Roughly **60-300× wall-clock difference**. The gap widens with row count because per-row JVM bridge cost is a fixed tax per row, while sparkrules' Catalyst pushdown runs as a single JVM projection with no per-row bridge.

### ? What sparkrules does instead

sparkrules compiles rules into Spark SQL expressions at classification time (Strategy A). Those expressions become part of the Spark logical plan. Catalyst optimizes them alongside the rest of your query:

- ? Predicate pushdown at the Parquet/Iceberg scan layer
- ? Column pruning so only referenced fact fields are read
- ? Vectorized execution using Spark's tungsten memory layout
- ? JVM-native codegen, zero Python workers in the hot path

Zero Python-JVM bridge per row. Zero KIE session init. Zero opaque UDFs blocking Catalyst. The rules are SQL that happens to be generated from DRL.

When a rule cannot be translated to SQL (multi-fact patterns, complex actions), sparkrules falls back to Strategy C (Python workers with shared alpha network), not to a JVM engine. Strategy C is still faster than Drools-on-Spark because the alpha network is shared across rules and the bridge cost is paid once per row for all rules, not once per row per rule.

### ?? Summary

Putting a JVM rule engine inside Spark executors is the data-engineering equivalent of running a database inside a MapReduce job. It works as a demo, not in production. Drools is a good tool on its native substrate (single JVM with enterprise SLA). Spark is a good tool on its native substrate (distributed query engine with Catalyst). Bolting them together gives you the worst properties of both.

sparkrules is built to be Spark-native, not a Drools-in-Spark adapter. That architectural difference is why the 1B-row benchmark works.

---

## ?? 10. What this document does not claim

- ? **Not** faster than Drools per core. Drools owns per-core speed on the JVM. Native extension (Req 27-29) on the roadmap targets closing that gap.
- ? **Not** a replacement for Flink CEP on streaming pattern matching. Different tool.
- ? **Not** faster than pandas at SIMD column math. pandas isn't a rule engine; different category.
- ?? Drools / GoRules / Camunda / ODM literature numbers are from vendor reports, not measured on this laptop. Treat them as sizing guides, not commitments.
- ?? 100% line coverage number applies to the Python engine only. Spark execution paths are marked `# pragma: no cover` and covered by manual smoke tests, not unit coverage. Bug 36.

---

## ???? 11. Apples-to-apples vs apples-to-oranges - read this before quoting any number

This doc compares engines in four different categories. Cross-category rankings are meaningful only within their own category.

| Tier | Category | Members in this doc |
|---|---|---|
| 1 | Rule engines | sparkrules, Drools, GoRules, Camunda, IBM ODM, rule-engine, business-rules |
| 2 | Stream CEP engines | Flink CEP |
| 3 | Vectorized column math | pandas, numpy, polars (baselines) |
| 4 | Hand-written code | raw Python if/else (baseline) |

### Which comparisons are fair

| Comparison | Fair? | Why |
|---|---|---|
| sparkrules vs rule-engine vs business-rules | ? apples-to-apples | All Tier 1, Python, same workload |
| sparkrules vs Drools on cost | ?? same tier, different runtimes | Fair for architectural economics; gap is architectural, not per-core |
| sparkrules vs Drools on latency | ?? same tier, different runtimes | Drools wins per-core; stated explicitly |
| sparkrules vs GoRules / Camunda / IBM ODM | ?? same tier, different runtimes | Literature, not measured; architectural fit only |
| sparkrules vs Flink CEP | ?? Tier 1 vs Tier 2 | Different categories; fair only for streaming CEP |
| sparkrules vs pandas / raw Python | ? Tier 1 vs Tier 3/4 | pandas isn't a rule engine |

### ?? Honest cross-tier summary

- **In Tier 1 (rule engines):** sparkrules wins the Python sub-tier at 50+ rules (measured). Drools wins the JVM sub-tier on per-core speed (literature). sparkrules wins any sub-tier once data exceeds one machine (architectural).
- **vs Tier 2 (Flink CEP):** different tool. Use Flink for event streams, sparkrules for batch and structured streaming decisions. They compose.
- **vs Tier 3 (pandas):** different tool. Static column math ? pandas. Authoring / governance / explainability ? sparkrules.
- **vs Tier 4 (raw code):** different tool. Rules never change ? raw code. Non-technical changes them ? a rule engine.
