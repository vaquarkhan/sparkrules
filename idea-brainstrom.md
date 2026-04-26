# AI Reproduction Blueprint — SparkRules

This document contains everything an AI code generator needs to rebuild the
SparkRules engine from scratch when given a single user prompt. It is
self-contained: architecture, data models, algorithms, file layout, test
strategy, correctness properties, and the exact prompt sequence that produced
the current implementation.

If you are an AI reading this, treat every section as ground truth. The
existing spec documents under `.kiro/specs/spark-rule-engine/` are the
canonical requirements (`requirements.md`), design (`design.md`), and
implementation plan (`tasks.md`) — this file summarises and augments them
with step-by-step reproduction guidance.

## Table of Contents

1. Product summary
2. User prompt template
3. Stack + environment
4. High-level architecture
5. Component inventory (module-by-module)
6. Data models
7. Correctness properties (P1–P38)
8. Test strategy
9. Directory layout
10. Reproduction sequence (ordered task list)
11. Known deviations and rationale
12. Extension roadmap


## 1. Product Summary

**Name:** SparkRules
**Purpose:** A distributed Drools-equivalent rule engine on Apache Spark 4 for
evaluating thousands of configurable business rules against billions of
transactions in seconds.

**Target workloads:**
- Legacy POS modernization with two-pass quota/discount logic
- Credit card authorization (low-latency streaming)
- Balance and settlement (batch, replayable)
- Underwriting (thousands of rules with reason codes)

**Drools feature parity goals:**
- DRL-equivalent syntax
- Salience, agenda groups, activation groups
- Decision tables with hit policies
- Forward + backward chaining
- Dynamic rule reload without redeploy
- Rule templates and guided editors
- Version history, effective dates, soft delete, audit log

**Spark 4 features leveraged (in the Scala port; the reference implementation
is pure Python):**
- Spark Connect for client separation
- VARIANT type for flexible rule definitions
- Python UDTFs for polymorphic outputs
- `transformWithState` for stateful streaming
- Apache Iceberg for ACID, time travel, schema evolution


## 2. User Prompt Template

A user who wants to rebuild SparkRules from scratch should provide a prompt
like this:

> Build a distributed Drools-equivalent business rule engine on Apache Spark 4
> for evaluating thousands of configurable rules against billions of transactions.
> Support POS end-of-day with two-pass quota rules, credit card auth streaming,
> settlement replay, and underwriting. Use a hybrid execution model: predicate
> pushdown, DataFrame-native, broadcast + mapPartitions, and SQL join. Store
> rules in a versioned metadata store with effective dates, soft delete,
> activation groups, salience, agenda groups. Include a DRL parser with
> pretty-printer, XLSX decision-table import/export, guided rule templates,
> rule simulator, A/B testing, snapshot-based replay, Prometheus metrics,
> Kubernetes manifests, and property-based tests for every invariant.

An AI processing this prompt should:

1. Read `.kiro/specs/spark-rule-engine/requirements.md` as ground truth
   requirements (34 requirements, EARS format).
2. Read `.kiro/specs/spark-rule-engine/design.md` for architecture, data
   models, execution strategies, and the 38 correctness properties.
3. Read `.kiro/specs/spark-rule-engine/tasks.md` for the 25-task
   implementation plan with property-test pairings.
4. Follow the reproduction sequence in section 10 of this document.


## 3. Stack and Environment

### Reference implementation (Python)

- Python 3.11+ (tested on 3.13)
- FastAPI for REST
- pydantic v2 for DTOs
- openpyxl for XLSX
- prometheus-client for metrics
- structlog for JSON logs
- httpx for client SDK
- pytest + hypothesis for tests
- pyyaml for k8s manifest validation

### Production port (Scala, per design.md)

- Scala 2.13 + sbt
- Apache Spark 4.0
- Apache Iceberg 1.5+
- ANTLR4 for DRL parser
- Apache POI for XLSX
- Spring Boot (Java 17) for REST
- ScalaTest + ScalaCheck for tests

### Why Python for the reference

The reference implementation is Python because:
- The sandbox had no Scala/sbt/Maven/Spark
- Every architectural component, data model, and property is preserved 1:1
- All 38 correctness properties are verifiable with pure-Python pytest + hypothesis
- The design document remains the canonical reference for a Scala port

### Dev setup commands

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest tests/ -q
```


## 4. High-Level Architecture

```
+---------------------+      +----------------------+
|  Authoring Plane    |      |  Metadata Plane      |
|  - Guided editor    |----->|  - rules (Iceberg-   |
|  - DT editor        |      |    like)             |
|  - XLSX importer    |      |  - run_history       |
|  - Simulator        |      |  - ab_tests          |
+---------------------+      +----------------------+
           |
           v
+---------------------------------------------------+
|  Control Plane                                     |
|  - REST API (FastAPI)                              |
|  - ConnectServer (in-proc; gRPC in Scala port)     |
|  - AuthN/Z (X-Principal header / OIDC in prod)     |
+---------------------------------------------------+
           |
           v
+---------------------------------------------------+
|  Driver                                            |
|  - RuleLoader                                      |
|  - RuleCompiler (Parser -> AST -> Classifier ->    |
|    Batcher -> DiscriminationNetwork)               |
|  - RuleBroadcaster (chunked)                       |
|  - AgendaController                                |
|  - StreamingRuleRefresher                          |
+---------------------------------------------------+
           |
           v
+---------------------------------------------------+
|  Executor Plane                                    |
|  - RuleExecutor (per-strategy dispatch)            |
|  - DiscriminationNetwork evaluation                |
|  - Per-fact exception isolation                    |
|  - Reason-code emission + fallback                 |
+---------------------------------------------------+
           |
   +-------+-------+
   v               v
+------+       +---------+
|Batch |       |Streaming|
|Eval  |       |Eval     |
+------+       +---------+
   |               |
   v               v
+----------+   +--------------------+
|rule_     |   |auth_decisions,     |
|results,  |   |rule_results,       |
|quota_    |   |run_history         |
|aggregates|   +--------------------+
|run_      |
|history   |
+----------+
```

### Execution strategies (hybrid model)

| Rule shape | Strategy | When chosen |
|---|---|---|
| Simple threshold/filter on scan column | PUSHDOWN | Catalyst pushes filter into Iceberg scan |
| Single-fact column expressions | DATAFRAME | Catalyst-fused `select` with CASE WHEN |
| Complex conditions, state, chaining, reason codes with bound fields | BROADCAST | `mapPartitions` with broadcast compiled rule package |
| Cross-fact patterns (multiple fact types) | SQL_JOIN | Catalyst picks broadcast or sort-merge join |

### Two-pass quota evaluation (POS workload)

```
POS facts -> Pass_1 rules (per-row classification)
          -> filter qualified=true
          -> groupBy(group_by_keys) -> aggregate (SUM/COUNT/TOP_N)
          -> Pass_2 rules (threshold / top-N / first-M on aggregates)
          -> emit rule_results per contributing fact
```

**Invariant (Property 28):** Pass 2 sees only Pass-1-qualified facts.
**Invariant (Property 29):** Pass 2 committed_ts >= Pass 1 committed_ts.


## 5. Component Inventory

Every module lives under `src/sre/`. In a rename to `sparkrules`, replace the
root package accordingly.

### `src/sre/model/`

| File | Public surface |
|---|---|
| `rule.py` | `Rule`, `RuleDefinition`, `Pass` enum, `RuleStatus`, `new_rule_id()`, `DEFAULT_AGENDA_GROUP` |
| `decision_table.py` | `DecisionTable`, `HitPolicy` (UNIQUE/FIRST/PRIORITY/COLLECT), `InputColumn`, `OutputColumn`, `Row`, `ColumnType`, `OverlappingRowsError`, `to_json`, `from_json` |
| `rule_template.py` | `RuleTemplate`, `ast_from_template`, `MissingPlaceholderError`, `ExtraPlaceholderError` |

All dataclasses are `frozen=True, slots=True` where feasible.

### `src/sre/parser/`

| File | Public surface |
|---|---|
| `ast.py` | `RuleAst`, `FactPattern`, `Predicate`, `BinaryOp`, `Not`, `Identifier`, `Literal`, `ListExpr`, `Action`, `ParseError` |
| `lexer.py` | `tokenize()`, `Token` |
| `parser.py` | `DrlParser`, `parse()` |
| `printer.py` | `DrlPrinter`, `print_ast()` |

Grammar covers: `rule`, `salience`, `agenda_group`, `activation_group`,
`pass`, `group_by`, `reason_codes`, `when` with `$binding : FactType(...)`
patterns, `then` with `result.field = expr;` actions. Operators: `==`, `!=`,
`<`, `<=`, `>`, `>=`, `and`, `or`, `not`, `in`, `not in`, `contains`, `matches`.

### `src/sre/store/`

| File | Public surface |
|---|---|
| `metadata_store.py` | `RuleMetadataStore`, `RuleFilter`, `ConflictError`, `UnknownRuleError` |

In-memory reference implementation. Operations: `insert`, `update`,
`soft_delete`, `activate`, `get`, `get_by_id`, `resolve(handle, t)`, `list(filter)`,
`list_versions(handle)`, `active_set_version(t)` (sha256 hash of active
`(handle, version)` pairs).

### `src/sre/ioxls/`

Package name chosen to avoid collision with stdlib `io`.

| File | Public surface |
|---|---|
| `exporter.py` | `DecisionTableExporter.export(dt, path)` |
| `importer.py` | `DecisionTableImporter.import_file(path) -> ImportResult`, `ImportError`, `CellTypeError`, `ImportResult` |

Layout: row 1 = metadata markers (`RuleTable`, name, `HIT_POLICY`, value);
row 2 = kind markers (`CONDITION`/`ACTION`); row 3 = names; row 4 = field_refs;
row 5 = types (`INT`/`FLOAT`/`STRING`/`BOOL`); row 6 = operators; row 7 = headers;
rows 8+ = data. Trailing `priority` column only when any row has non-zero priority.

### `src/sre/compiler/`

| File | Public surface |
|---|---|
| `evaluator.py` | `evaluate_expr`, `evaluate_rule`, `RuleMatch` — reference oracle |
| `classifier.py` | `Strategy` (PUSHDOWN/DATAFRAME/BROADCAST/SQL_JOIN), `StrategyClassifier` |
| `batcher.py` | `RuleBatch`, `RuleBatcher` (default batch_size=200) |
| `discrimination.py` | `AlphaNode`, `DiscriminationNetwork.build()/evaluate()` with `eval_counter` |
| `compiler.py` | `RuleCompiler.compile()`, `CompiledRulePackage.serialize()/deserialize()` |

### `src/sre/transport/`

| File | Public surface |
|---|---|
| `broadcaster.py` | `Broadcast[T]` (eager + lazy), `BroadcastChunk`, `RuleBroadcaster` with threshold + chunking |

### `src/sre/executor/`

| File | Public surface |
|---|---|
| `agenda.py` | `AgendaController.order_activations()`, `resolve_activation_groups()`, `forward_chain()`, `ChainingLimitExceededError` |
| `rule_executor.py` | `RuleExecutor.evaluate(facts)`, `FactResult` |

### `src/sre/runtime/`

| File | Public surface |
|---|---|
| `iceberg_store.py` | `IcebergLikeTable` (snapshot-per-mutation, row-level deletes, pickle-safe), `UnknownSnapshotError` |
| `batch.py` | `BatchEvaluator`, `BatchEvaluationSpec`, `RunRecord` |
| `streaming.py` | `StreamingEvaluator`, `StreamingRuleRefresher`, `StatefulContext`, `MicroBatchResult`, `default_executor_factory` |
| `two_pass.py` | `TwoPassOrchestrator`, `TwoPassResult`, `QuotaAggregate` |
| `catalyst.py` | `CatalystConfigurer`, `KNOWN_CATALYST_RULES`, `UnknownCatalystRuleError` |
| `cache.py` | `DerivedColumnCache` |

### `src/sre/sim/`

| File | Public surface |
|---|---|
| `simulator.py` | `RuleSimulator`, `SimulationResult` |
| `ab.py` | `ABTestRunner`, `ABTestConfig`, `Variant` |
| `replay.py` | `ReplayService`, `MissingRuleSetVersionError` |

### `src/sre/api/`

| File | Public surface |
|---|---|
| `app.py` | `create_app(deps)`, `AppDeps` |
| `schemas.py` | pydantic models: `RuleCreateRequest`, `RuleResponse`, `SimulationRequest`, `SimulationResponse`, `RunSubmissionRequest`, etc. |

### `src/sre/connect/`

| File | Public surface |
|---|---|
| `server.py` | `ConnectServer` (in-process dispatch; gRPC in Scala port) |

### `src/sre/client/`

| File | Public surface |
|---|---|
| `sdk.py` | `SreClient` (HTTP or in-process), `SreClientError`, `install_transient_failure` (test helper) |

### `src/sre/obs/`

| File | Public surface |
|---|---|
| `metrics.py` | `SreMetrics`, `metrics_endpoint_app(registry)` |
| `logging.py` | `configure_logging`, `bind_run_context`, `get_logger` |


## 6. Data Models

### Rule (canonical)

```python
@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: UUID
    rule_handle: str
    version: int
    rule_group: str
    salience: int
    effective_from: datetime
    effective_to: datetime | None
    is_active: bool
    rule_definition: RuleDefinition  # source + format (DRL | DECISION_TABLE_JSON)
    activation_group: str | None
    reason_codes: tuple[str, ...] = ()
    pass_: Pass = Pass.SINGLE
    group_by_keys: tuple[str, ...] = ()
    source_file_hash: str | None = None
    author_principal: str = "system"
    created_at: datetime = now_utc
```

### RuleMetadataStore invariants

- Insert: allocates new `version = max+1` per `rule_handle`.
- Overlap: same `rule_handle` with overlapping effective windows AND both
  `is_active=True` -> `ConflictError`.
- Resolve: returns highest-version active rule whose window covers `t`.
- Soft delete: flips `is_active=False` on every version; retains all history.
- Activate: can re-activate an inactive version if no active version overlaps.
- `active_set_version(t)` = sha256 of sorted active `(handle, version)` tuples.

### IcebergLikeTable

```python
class IcebergLikeTable:
    name: str
    schema: dict[str, type]
    _snapshots: dict[int, list[dict]]
    _current_snapshot_id: int

    def append(rows) -> int: ...        # returns new snapshot_id
    def snapshot(snapshot_id) -> list[dict]: ...
    def delete_rows(predicate) -> int: ...  # new snapshot, row-level delete
    def current_snapshot_id() -> int: ...
    def row_count(snapshot_id) -> int: ...
```

Every mutation creates a new snapshot; old snapshots remain readable and
byte-stable. Supports pickle round-trip for serialization.

### RunRecord

```python
@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str              # uuid4
    mode: str                # "BATCH" | "STREAMING"
    input_table_name: str
    input_snapshot_id: int | None
    rule_set_version: str    # sha256 of active rule set
    config_fingerprint: str
    start_ts: datetime
    end_ts: datetime | None
    facts_processed: int
    rules_fired: int
    rules_errored: int
    status: str              # "RUNNING" | "SUCCESS" | "FAILED" | ...
    error_class: str | None
    error_message: str | None
    replay_source_run_id: str | None
```

### FactResult (rule_results row shape)

```python
@dataclass(frozen=True, slots=True)
class FactResult:
    fact_id: str
    rule_id: str
    rule_handle: str
    version: int
    pass_: str
    fired: bool
    reason_codes: tuple[str, ...]
    bound_fields: dict[str, Any]   # every identifier from constraints
    action_output: dict[str, Any]  # result.* assignments
    error_class: str | None
    error_message: str | None
```

### CompiledRulePackage

```python
@dataclass
class CompiledRulePackage:
    rule_set_version: str
    batches: list[RuleBatch]
    discrimination_networks: dict[str, DiscriminationNetwork]  # per BROADCAST batch
    strategy_by_rule_id: dict[str, Strategy]
    rule_asts_by_id: dict[str, RuleAst]
    metadata: dict[str, Any]

    def serialize() -> bytes: ...   # pickle (Kryo in Scala port)
    @staticmethod
    def deserialize(data) -> CompiledRulePackage: ...
```


## 7. Correctness Properties (P1–P38)

Every property is universally quantified and must be implemented as a
property-based test with `hypothesis` (or ScalaCheck in the Scala port).
Minimum 100 iterations (perf-sensitive ones down to 30-60).

| # | Property | Requirement | Test file |
|---|---|---|---|
| P1 | Rule resolver correctness | Req 1.5 | tests/property/test_store_properties.py |
| P2 | Version retention across updates | Req 1.4 | tests/property/test_store_properties.py |
| P3 | Overlapping effective window rejected | Req 1.6 | tests/property/test_store_properties.py |
| P4 | List-with-filters matches reference filter | Req 2.5 | tests/property/test_list_filters_property.py |
| P5 | Soft-delete retention | Req 2.4 | tests/property/test_store_properties.py |
| P6 | DRL round-trip (parse -> print -> parse) | Req 3.5 | tests/property/test_drl_properties.py |
| P7 | Parser reports unresolved identifiers | Req 3.3 | tests/property/test_drl_properties.py |
| P8 | Hit policy semantics | Req 4.2, 4.4, 4.5 | tests/property/test_decision_table_properties.py |
| P9 | XLSX import round-trip | Req 5.2 | tests/property/test_xlsx_properties.py |
| P10 | XLSX type mismatch reports exact cells | Req 5.3 | tests/property/test_xlsx_properties.py |
| P11 | Rule template instantiation equivalence | Req 6.3 | tests/property/test_template_properties.py |
| P12 | Template missing-placeholder diagnostic | Req 6.4 | tests/property/test_template_properties.py |
| P13 | Forward chaining termination | Req 7.2, 7.4 | tests/property/test_agenda_properties.py |
| P14 | Agenda ordering | Req 8.1-8.3 | tests/property/test_agenda_properties.py |
| P15 | Activation-group mutual exclusion | Req 9.1-9.3, 30.5 | tests/property/test_agenda_properties.py |
| P16 | Broadcast chunk round-trip | Req 10.4 | tests/property/test_broadcaster_properties.py |
| P17 | Strategy-equivalence | Req 11.1-11.4 | tests/property/test_compiler_properties.py |
| P18 | Rule batching equivalence | Req 12.3 | tests/property/test_compiler_properties.py |
| P19 | Discrimination network equivalence | Req 13.3 | tests/property/test_compiler_properties.py |
| P20 | Shared sub-predicate single-evaluation | Req 13.2 | tests/property/test_compiler_properties.py |
| P21 | Derived column caches unpersisted at run end | Req 15.2 | tests/property/test_cache_properties.py |
| P22 | State TTL expiration | Req 17.3 | tests/property/test_streaming_properties.py |
| P23 | Compilation failure never replaces prior broadcast | Req 18.3 | tests/property/test_streaming_properties.py |
| P24 | Simulator never persists | Req 19.1 | tests/property/test_ab_properties.py |
| P25 | A/B deterministic assignment | Req 20.2, 20.3 | tests/property/test_ab_properties.py, test_client_properties.py |
| P26 | Decision table JSON round-trip | Req 23.3 | tests/property/test_decision_table_properties.py |
| P27 | Per-rule per-fact exception isolation | Req 24.1 | tests/property/test_executor_properties.py |
| P28 | Pass-2 visibility | Req 26.6, 26.7 | tests/property/test_twopass_properties.py |
| P29 | Pass-2 aggregate-then-rule correctness and ordering | Req 26.3-26.5 | tests/property/test_twopass_properties.py |
| P30 | POS determinism invariant | Req 27.4, 27.5 | tests/property/test_replay_properties.py |
| P31 | Auth determinism invariant | Req 28.4 | tests/property/test_replay_properties.py |
| P32 | Underwriting determinism invariant | Req 30.3 | tests/property/test_replay_properties.py |
| P33 | Mode-parity invariant (batch = streaming) | Req 31.3 | tests/property/test_streaming_properties.py |
| P34 | ACID partial-write invisibility | Req 32.2 | tests/property/test_batch_properties.py |
| P35 | Snapshot read-stability | Req 32.7 | tests/property/test_batch_properties.py |
| P36 | Replay determinism | Req 33.3, 27.4, 29.4 | tests/property/test_replay_properties.py |
| P37 | Reason code subset of declared list | Req 34.2, 34.6 | tests/property/test_executor_properties.py |
| P38 | Explanation sufficiency | Req 34.3 | tests/property/test_executor_properties.py |

Each test must carry a comment or docstring of the form:

```python
"""Feature: spark-rule-engine, Property N: <short description>.

Validates: Requirement X.Y.
"""
```


## 8. Test Strategy

### Tiers

| Tier | Purpose | Count | Runtime |
|---|---|---|---|
| Unit (`tests/unit/`) | Example-based coverage of every component | ~150 | seconds |
| Property (`tests/property/`) | Universal invariants P1-P38 | ~50 (100-examples each) | ~30s |
| Integration (`tests/integration/`) | End-to-end use cases | 4 modules (~10 tests) | <5s each |
| Perf (`tests/perf/`) | Opt-in regression gate | 1 | ~20s |

### Default test command

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

Must output: `234 passed, 1 deselected`. The deselected test is the perf
benchmark, excluded by default via `addopts = "-m 'not perf'"` in
`pyproject.toml`.

### Perf test command

```powershell
.\.venv\Scripts\python.exe -m pytest tests/perf -m perf -q
```

### hypothesis profile

Standard profile:

```python
PROFILE = settings(
    max_examples=100,   # 50 for expensive perf; 30 for xlsx/spark-heavy
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.data_too_large,
    ],
)
```

### Integration use cases

| File | Workload | Key assertions |
|---|---|---|
| `test_pos_end_of_day.py` | POS EoD with two-pass quota | 20 txns x 4 rules; Pass_1 qualification; Pass_2 customer-spend 5% discount fires exactly on qualifying customers; store audit flag on correct store; idempotent re-run produces equal multiset |
| `test_auth_streaming.py` | Auth streaming with mid-stream rule refresh | 5 micro-batches x 10 facts; new rule inserted between batches 2 and 3; rule_set_version changes only then; velocity state with TTL; mode parity vs batch |
| `test_settlement_replay.py` | Settlement + chargeback replay | 30 settlements; delete_rows correction creates new snapshot; replay re-reads original snapshot; replay_source_run_id set; multiset equality |
| `test_underwriting.py` | Underwriting with activation groups | 50 apps x 3 product lines x 20 rules; exactly one fire per activation_group per app; non-empty reason codes; determinism across two runs |

### Markers (in `pyproject.toml`)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers -m 'not perf'"
markers = [
  "property: property-based tests (hypothesis)",
  "integration: integration tests requiring Spark/Iceberg",
  "slow: long-running tests",
  "perf: opt-in performance benchmarks (run with -m perf)",
]
```


## 9. Directory Layout

```
sparkrules/
|-- pyproject.toml                 # package metadata, deps, pytest markers
|-- README.md
|-- BUILD_STATUS.md
|-- AI_REPRODUCTION_BLUEPRINT.md   # this file
|-- .gitignore
|-- .kiro/
|   `-- specs/
|       `-- spark-rule-engine/
|           |-- requirements.md    # 34 EARS requirements
|           |-- design.md          # architecture + 38 properties
|           |-- tasks.md           # 25-task implementation plan
|           `-- .config.kiro
|-- deploy/
|   `-- k8s/
|       |-- namespace.yaml
|       |-- configmap.yaml
|       |-- secret.yaml.example
|       |-- rule-api.yaml          # Deployment + Service, /health probes
|       |-- connect.yaml           # Deployment + Service, gRPC-capable
|       |-- values-dev.yaml        # reference values (not Helm)
|       |-- values-prod.yaml
|       `-- README.md
|-- src/
|   `-- sre/                       # (rename to sparkrules/)
|       |-- __init__.py
|       |-- model/
|       |-- parser/
|       |-- store/
|       |-- ioxls/
|       |-- compiler/
|       |-- transport/
|       |-- executor/
|       |-- runtime/
|       |-- sim/
|       |-- api/
|       |-- connect/
|       |-- client/
|       `-- obs/
`-- tests/
    |-- __init__.py
    |-- unit/
    |-- property/
    |-- integration/
    `-- perf/
```


## 10. Reproduction Sequence

This is the exact ordered task list an AI should execute. Each task produces
runnable code end-to-end and is paired with at least one property-based or
example-based test. The original implementation shipped these in 8 delegation
waves — the AI can batch similarly or execute sequentially.

### Wave 1: Project bootstrap (Task 1)

1. Write `pyproject.toml` with deps, markers, test config.
2. Create `src/sre/__init__.py`, empty package dirs, `tests/*/__init__.py`.
3. Install with `pip install -e ".[test]"`.
4. Smoke test: `import sre` works, pytest collects.

### Wave 2: Rule model + store (Task 2)

1. `src/sre/model/rule.py` — `Rule`, `RuleDefinition`, `Pass`, `new_rule_id`.
2. `src/sre/store/metadata_store.py` — `RuleMetadataStore`, `RuleFilter`, `ConflictError`.
3. Tests: `test_rule_model.py`, `test_metadata_store.py`, plus P1, P2, P3, P5.

### Wave 3: DRL parser (Task 3)

1. `src/sre/parser/ast.py`, `lexer.py`, `parser.py`, `printer.py`.
2. Hand-rolled recursive-descent parser (or ANTLR4 in Scala port).
3. Tests: `test_drl_parser.py`, plus P6 (round-trip) and P7 (unresolved identifiers).

### Wave 4: Decision tables + XLSX + templates (Tasks 4, 5, 6)

1. `src/sre/model/decision_table.py` — hit policies, evaluator, JSON round-trip.
2. `src/sre/ioxls/` — exporter + importer with per-cell error list.
3. `src/sre/model/rule_template.py` — placeholders + DRL expansion.
4. Tests: P8 (hit policy), P9/P10 (XLSX), P11/P12 (templates), P26 (DT JSON).

### Wave 5: Compiler + transport + runtime primitives (Tasks 7-11)

1. `src/sre/compiler/` — evaluator, classifier, batcher, discrimination network, compiler.
2. `src/sre/transport/` — broadcaster with chunking.
3. `src/sre/runtime/catalyst.py` + `runtime/cache.py`.
4. `src/sre/executor/rule_executor.py` + `executor/agenda.py`.
5. Tests: P13, P14, P15, P16, P17, P18, P19, P20, P21, P27, P37, P38.

### Wave 6: Runtime + simulation (Tasks 13-17)

1. `src/sre/runtime/iceberg_store.py` — snapshot-per-mutation.
2. `src/sre/runtime/batch.py` — BatchEvaluator with run_history.
3. `src/sre/runtime/streaming.py` — StreamingEvaluator + Refresher.
4. `src/sre/runtime/two_pass.py` — TwoPassOrchestrator.
5. `src/sre/sim/simulator.py`, `sim/ab.py`, `sim/replay.py`.
6. Tests: P22, P23, P24, P25, P28, P29, P30, P31, P32, P33, P34, P35, P36.

### Wave 7: REST API + client + observability (Tasks 18-20)

1. `src/sre/api/app.py` + `api/schemas.py` — FastAPI + pydantic.
2. `src/sre/connect/server.py` — in-process ConnectServer.
3. `src/sre/client/sdk.py` — SreClient with retries.
4. `src/sre/obs/metrics.py` + `obs/logging.py`.
5. Tests: REST contract, connect, SDK, DTO round-trip, P4 (list filters), metrics + logs.

### Wave 8: Integration + deployment + perf (Tasks 22-24)

1. `tests/integration/` — POS, auth streaming, settlement, underwriting.
2. `deploy/k8s/` — namespace, configmap, secret example, rule-api, connect, values.
3. `tests/perf/test_benchmark.py` — opt-in with `@pytest.mark.perf`.
4. `tests/unit/test_k8s_manifests.py` — PyYAML validation.

### Wave 9: Finalisation

1. Run `pytest tests/ -q` — expect **234 passed, 1 deselected**.
2. Run `pytest tests/perf -m perf -q` — expect **1 passed**.
3. Update `BUILD_STATUS.md` with the final count.


## 11. Known Deviations and Rationale

The reference implementation makes three deliberate deviations from the Scala
design document. An AI reproducing the project in Scala does **not** inherit
these deviations.

### 11.1 Host language — Python vs Scala

**Deviation:** Reference implementation is pure Python 3.11+ using FastAPI,
httpx, pydantic, openpyxl, pytest+hypothesis. The design calls for Scala 2.13
+ sbt + Spring Boot + Python client via Spark Connect gRPC.

**Reason:** Sandbox had no Scala/sbt/Maven/Docker. Python implementation
preserves every architectural component, data model, and correctness property
1:1. The design remains canonical for the Scala port.

**Impact on Scala port:** Use the same component boundaries and property
tests (ScalaCheck instead of hypothesis). No changes to requirements,
architecture, or data models.

### 11.2 SQL_JOIN strategy — stub only

**Deviation:** The `RuleExecutor` classifies and dispatches SQL_JOIN rules
but returns `error_class="SqlJoinNotImplemented"` for the pure-Python runtime.

**Reason:** Cross-fact rule evaluation over real joins requires Spark; out of
scope for the Python reference.

**Impact on Scala port:** Implement `SqlJoinStrategy` that emits a Spark SQL
`SELECT` with joins between Fact DataFrames; Catalyst picks broadcast vs
sort-merge based on statistics. P17 (strategy equivalence) must then include
SQL_JOIN cases.

### 11.3 Spark Connect gRPC — in-process

**Deviation:** `ConnectServer` is a Python object dispatched via method
calls; the client SDK speaks either HTTP (to FastAPI) or direct method calls.

**Reason:** No gRPC runtime in the sandbox.

**Impact on Scala port:** Replace with real Spark Connect gRPC server
(embedded in the driver) and a thin client holding only a gRPC channel.
Method surface and contract remain identical.

### 11.4 Performance harness — reduced scale

**Deviation:** Perf test runs 50 rules x 10,000 facts (smoke mode) rather
than the Phase-1 target of 500 rules x 1M facts.

**Reason:** Pure-Python evaluator runs at ~500 facts/s at 50 rules; full
scale would take ~200s. Structural shape (rule strategy mix, deterministic
inputs, budget assertion) is preserved.

**Impact on Scala port:** Run the full Phase-1 benchmark against a reference
small Spark cluster; expect <30s wall-clock.


## 12. Extension Roadmap

These are features the reference implementation does NOT include but the
architecture is explicitly designed to accept. An AI extending the project
should follow this ordering.

### 12.1 Web UI (React + Monaco + AG Grid)

MVP screens that map onto existing REST endpoints:

| Screen | Backend endpoint it wraps |
|---|---|
| Rules list with enable/disable toggle | `GET /rules`, `POST /rules/{h}/activate`, `DELETE /rules/{h}` |
| DRL rule editor with parse-error highlighting | `POST /rules` (catches ParseError -> 400 with line/column) |
| Decision table editor (grid) | `POST /rules` with `RuleDefinition(format=DECISION_TABLE_JSON)` |
| XLSX upload page | `POST /decision-tables/import` |
| Simulator page | `POST /simulations` |
| Run history + replay | `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/replay` |
| Version diff viewer | `GET /rules/{h}/versions/{v1}` + `/{v2}`, pretty-print + diff |
| A/B test configurator | `POST /ab-tests` |

Stack: React + TypeScript + Vite + TanStack Query + shadcn/ui. Monaco for
DRL editor. AG Grid for decision tables. Under `ui/`.

### 12.2 Scala port (production path)

Replace Python modules one-for-one with Scala equivalents. ANTLR4 grammar
(`Drl.g4`) replaces the hand-rolled Python parser. sbt multi-module:
`engine-core`, `rule-api` (Spring Boot), `spark-connect-server`. ScalaCheck
ports every property test.

### 12.3 Real Spark execution

Wire the Scala executor into Spark:
- PUSHDOWN: emit `Filter` node on the DataFrame scan; Iceberg pushes it down.
- DATAFRAME: emit fused `select` with `CASE WHEN ... THEN named_struct(...) END`.
- BROADCAST: `mapPartitions` with the broadcast CompiledRulePackage.
- SQL_JOIN: emit `SELECT` with joins; Catalyst chooses broadcast vs sort-merge.

### 12.4 Real Iceberg

Replace `IcebergLikeTable` with `pyiceberg` (Python) or native Iceberg
catalog (Scala). Snapshot semantics already match; swap the import.

### 12.5 Real Spark Connect gRPC

Replace `ConnectServer` Python class with a Spark Connect plugin extension.
Client SDK swaps from `httpx` to `grpcio` for the Connect path.

### 12.6 Multi-tenancy + RBAC

- Extract `tenant_id` from the OIDC claim in `X-Principal`.
- Scope every Iceberg namespace and metric label by tenant.
- Add RBAC roles: `rule_reader`, `rule_author`, `rule_admin`, `run_operator`,
  `platform_admin`.

### 12.7 Audit log table

Append-only Iceberg table `audit_log` with `(ts, principal, action, resource,
request_hash, response_status)`. Already accounted for in design.md section
"Security and Multi-Tenancy".

### 12.8 Advanced Drools parity

Remaining gaps vs Drools Business Central (already mapped in section 5 of
this document):
- Guided rule editor UI (backend AST model ready)
- Rule templates UI (backend model ready)
- Git-backed rule project persistence
- Rule test scenarios UI (simulator endpoint ready)
- Multi-project workspaces


## 13. Quick-Start for an AI Code Generator

Minimal prompt:

> Read `.kiro/specs/spark-rule-engine/requirements.md`,
> `.kiro/specs/spark-rule-engine/design.md`, and
> `.kiro/specs/spark-rule-engine/tasks.md`. Then read
> `AI_REPRODUCTION_BLUEPRINT.md` for the reproduction sequence. Implement the
> project in Python 3.11+ following the 25-task plan. Pair every
> implementation task with at least one property or example test. All 38
> correctness properties must be verified by hypothesis-driven tests. Target:
> 234 tests passing (+1 opt-in perf).

The AI should then execute the 9 waves in section 10, running pytest after
each wave. If any wave fails, fix before proceeding.

Final validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
# expected: 234 passed, 1 deselected

.\.venv\Scripts\python.exe -m pytest tests/perf -m perf -q
# expected: 1 passed
```


## 14. Reference Files

The three spec documents under `.kiro/specs/spark-rule-engine/` are the
canonical inputs:

| File | Purpose | Size |
|---|---|---|
| `requirements.md` | 34 EARS requirements across 3 workload families | ~13k words |
| `design.md` | Architecture, components, data models, 38 correctness properties | ~18k words |
| `tasks.md` | 25-task implementation plan with property-test pairings | ~2k words |

All three are required reading. This blueprint augments them with:
- Reproduction sequence (section 10)
- Known deviations (section 11)
- Extension roadmap (section 12)
- Quick-start prompt (section 13)
- Directory layout (section 9)
- Stack + environment setup (section 3)


---

**Generated:** April 2026
**Engine state:** 234 tests passing, 38/38 correctness properties covered,
4 integration use cases green, 25/25 tasks complete.

For the canonical architecture, always consult
`.kiro/specs/spark-rule-engine/design.md`. This blueprint is a reproduction
aid; the design document is the source of truth.


---

# Part II — Product Extensions

The sections below describe planned product extensions beyond the current 234-test
reference implementation. Each extension reuses the existing engine, parser, store,
simulator, executor, and replay infrastructure — they are NOT forks. An AI code
generator should treat each extension as an additive spec tree that plugs into
the existing `src/sre/` package.

## 15. Product Positioning

### 15.1 What makes this a niche product

Three tiers of differentiation.

**Tier 1 — Features no existing product combines**

1. **Two-pass quota rules as a first-class concept**
   Pass 1 per-row classification, Pass 2 aggregate-then-rule on qualified facts.
   Properties P28 (visibility) and P29 (ordering + aggregate correctness) proven.
   Drools can't do this natively; Spark SQL lacks the rule-engine semantics.

2. **Replay determinism pinned to Iceberg snapshots**
   Every run records `(snapshot_id, rule_set_version, config_fingerprint)`.
   Months later: reproduce exact `rule_results` multiset. Property P36.

3. **Mode-parity invariant** (batch = streaming)
   Same `(rule_handle, version)` produces identical results in both modes.
   Property P33. No existing engine proves this.

4. **Property-verified correctness** — 38 universal invariants machine-verified.
   Regulators and risk teams get *proof*, not example tests.

5. **Explanation sufficiency** (P38) — fired rules carry bound_fields
   sufficient to re-evaluate without the original fact.

**Tier 2 — Individually available, combined rarely**

6. Drools-equivalent authoring + Spark-scale execution under one config.
7. Dynamic rule refresh without redeploy (P23).
8. Hybrid execution strategy per rule, not per job.
9. Snapshot-isolated rule catalog (`rule_set_version` hash).
10. XLSX round-trip with exhaustive per-cell error reporting (P10).

**Tier 3 — Table stakes**

Versioned metadata, soft delete, effective dates, salience, agenda + activation
groups, decision tables with four hit policies, forward/backward chaining,
derived column caching, Catalyst per-rule toggles, Prometheus metrics,
structured JSON logs, rule simulator, A/B testing, per-rule per-fact exception
isolation.

### 15.2 Why this gap exists in the market

Existing tooling splits three ways, no single product spans all three:

| Bucket | Examples | Gap |
|---|---|---|
| Mature rule engines | Drools, Easy Rules, GoRules ZEN | Single-JVM; no Iceberg, snapshot replay, distributed shuffle |
| Spark-native rule snippets | databrickslabs/dataframe-rules-engine, blog-post integrations | Thin validation layer; no Drools configurability (salience, activation groups, chaining, versioning) |
| Commercial decision platforms | FICO Blaze, IBM ODM, Pega, SAS | Closed-source, per-core licensing, not Spark-native |

Reasons no open-source product has glued them:

- Rule-engine skill set (PHREAK, DRL, decision tables) rarely overlaps with Spark internals skill set (Catalyst, shuffle, Iceberg).
- Red Hat Drools team focuses on Java/Quarkus, not Spark.
- Databricks focuses on ML + SQL, not Drools parity.
- Target market (high-volume transaction processors — POS, auth, settlement) is small but has no alternative.
- Spark 4 features (VARIANT, `transformWithState`, Spark Connect) only landed May 2025.
- Apache Iceberg matured 2023–2024.
- Two-pass quota is a POS pattern most rule-engine papers skip.
- Property-based correctness guarantees are rare in rule engines.

### 15.3 Positioning lines by buyer

| Audience | Line |
|---|---|
| Risk / compliance | "Deterministic, replayable rule evaluation for regulated workloads — prove any decision, months later, byte-for-byte." |
| Platform engineers | "Drools authoring UX on Spark 4 scale, without gluing them yourself." |
| POS / payments product owners | "Two-pass quota rules — spend tiers, top-N kickers, first-M promos — as declarative business rules instead of Spark SQL." |
| Databricks shops | "Drools-equivalent rule management on top of Iceberg + Spark Connect, with snapshot-pinned replay." |


## 16. Phase 2a — Data Quality Extension

Data quality checks are rules with a specific shape: predicates over facts that
emit pass/fail with reason codes and severity. Everything SparkRules already
supports — this extension adds DQ-specific primitives on top.

### 16.1 Mapping

| DQ concept | SparkRules equivalent | Already built |
|---|---|---|
| Validation rule | Single-fact rule, side-effect-free action | ✅ |
| Row-level check | Pass_1 rule | ✅ |
| Aggregate check (row count, sum) | Pass_2 aggregate rule | ✅ |
| Reconciliation (fact matches reference) | SQL_JOIN strategy | ⚠️ classified, stub only |
| Schema check | Rule over field types | ⚠️ needs sugar primitive |
| Null / required check | Simple predicate | ✅ |
| Referential integrity | Cross-fact rule | ⚠️ classified, stub only |
| Freshness / staleness | Timestamp predicate | ✅ |
| Anomaly threshold | Aggregate rule w/ stddev/percentile | ⚠️ aggregates limited today |
| Quarantine / DLQ | FactResult with severity=ERROR | ⚠️ add severity field |
| Data contract | Declarative rule bundle per dataset | ⚠️ new concept |

### 16.2 New rule attributes

Extend `Rule` dataclass:

```python
severity: Literal["INFO", "WARN", "ERROR", "CRITICAL"] = "INFO"
scope: Literal["ROW", "DATASET", "RELATIONSHIP"] = "ROW"
data_contract_id: str | None = None
tolerance: float | int | None = None   # e.g. "≤0.1% nulls OK"
```

### 16.3 New rule shapes (sugar over existing primitives)

| Shape | Expands to |
|---|---|
| `ExpectColumnValuesToBeUnique(col)` | Pass_2 aggregate: `COUNT DISTINCT col == COUNT *` |
| `ExpectColumnValuesToMatchRegex(col, pattern)` | Predicate with `matches` op |
| `ExpectColumnSumToBeBetween(col, low, high)` | Pass_2 aggregate |
| `ExpectRowCountToBeWithin(low, high)` | Dataset-level aggregate |
| `ExpectTableCountsToMatch(a, b)` | Cross-dataset reconciliation |
| `ExpectColumnValuesToBeInSet(col, set)` | Predicate w/ `in` op |
| `FreshnessCheck(ts_col, max_age)` | Timestamp predicate |

All compile down to ordinary `RuleAst` — the compiler, executor, and simulator
are unchanged.

### 16.4 Data contract format

```yaml
contract: pos_transactions_v3
owner: retail-data-platform
rules:
  - id: dc_pos_001
    severity: CRITICAL
    scope: ROW
    drl: |
      rule "non_null_customer_id"
      when $t : PosTxn(customer_id == null)
      then result.violation = "NULL_CUSTOMER_ID"; end
    tolerance: 0
  - id: dc_pos_002
    severity: WARN
    scope: DATASET
    drl: |
      rule "daily_row_count_bounds"
        pass PASS_2
        group_by ["txn_date"]
      when $g : DailyCount(count < 1000 or count > 100000)
      then result.violation = "ROW_COUNT_OUT_OF_BOUNDS"; end
```

### 16.5 New run type + outputs

- `DqRun` — runs only DQ-scoped rules, emits a quality score.
- `run_history.summary.violations_by_severity`, `pass_rate`.
- New Iceberg table `dq_violations` keyed by `(run_id, fact_id, rule_id)`.
- Quarantine routing: facts firing `CRITICAL` rules can be written to a
  quarantine table before downstream consumption.

### 16.6 Dashboards and lineage

- Prometheus: `sparkrules_dq_pass_rate`, `sparkrules_dq_violations_by_severity`.
- OpenLineage events on every run with dataset inputs, outputs, rule bundle hash.

### 16.7 New correctness properties

| # | Property | Statement |
|---|---|---|
| P39 | Severity monotonicity | A rule's severity can only escalate without a version bump; demotions require new version. |
| P40 | Tolerance correctness | Rule with tolerance τ fires iff violation count > τ × total row count. |
| P41 | Quarantine completeness | Every fact triggering a CRITICAL rule appears exactly once in `dq_violations`. |
| P42 | Contract closure | Running a data contract produces exactly the union of results for its declared rules. |
| P43 | Reconciliation commutativity | `reconcile(A, B) = reconcile(B, A)` on fired-pair set. |

### 16.8 Competitive positioning vs DQ tools

| Tool | Strength | Gap vs SparkRules |
|---|---|---|
| Great Expectations | Expressive expectations, docs | Python library, no distributed runtime, no rule versioning |
| Soda Core / Cloud | YAML checks, UI | SQL-only, weak on complex business logic |
| dbt tests | SQL-native | Dataset-scoped, not event-scoped |
| Deequ (AWS Labs) | Spark-native constraint suggestion | Scala API, no business-user authoring, no replay |
| Monte Carlo / Bigeye / Anomalo | Observability, ML anomaly | Closed-source, don't cover complex business rules |
| Apache Griffin | Spark-based DQ | Abandoned, last release 2019 |

**SparkRules' unique combination:** Drools-style business rule authoring +
Spark-scale DQ execution + snapshot-based replay under one catalog.


## 17. Phase 2b — Runtime Profile Extension

The engine is runtime-agnostic by construction. The `CompiledRulePackage` is a
serializable artifact. The executor reads facts, evaluates, emits
`rule_results`. Neither knows or cares where it runs. This extension formalises
that as user-facing configuration.

### 17.1 Supported runtimes (via config only)

| Runtime | Backend implementation |
|---|---|
| Local Python process | `InProcessBackend` — reference impl |
| Spark on EMR | `SparkBackend` (YARN / cluster mode) |
| Spark on EMR Serverless | `EmrServerlessBackend` |
| Spark on EKS via Spark Connect | `SparkConnectBackend` |
| Spark on GKE | `SparkConnectBackend` or `SparkBackend` |
| AWS Glue | `GlueBackend` |
| Databricks (classic or serverless) | `DatabricksBackend` |
| Dataproc (GCP) | `DataprocBackend` |
| HDInsight (Azure) | `SparkBackend` |
| Synapse Spark Pools | `SparkBackend` |

### 17.2 Three abstractions

```python
class ExecutorBackend(Protocol):
    def evaluate(
        self,
        package: CompiledRulePackage,
        fact_source: FactSource,
        result_sink: ResultSink,
        *,
        run_id: str,
        snapshot_id: int | None = None,
    ) -> RunRecord: ...

class FactSource(Protocol):
    def read(self, snapshot_id: int | None) -> Iterable[dict]: ...
    def snapshot_id_for(self, ts: datetime | None) -> int: ...

class ResultSink(Protocol):
    def write(self, rows: Iterable[FactResult], run_id: str) -> int: ...
```

Source/Sink implementations:

| Type | Runtime |
|---|---|
| `IcebergLikeSource/Sink` | Reference in-memory (already built) |
| `IcebergSource/Sink` | pyiceberg or Spark Iceberg — Glue, Nessie, REST, Hive |
| `ParquetSource` | Legacy read-only |
| `DeltaSource/Sink` | Delta Lake (Databricks, open-source) |
| `KafkaSource` | Streaming |
| `KinesisSource` | AWS streaming |
| `JdbcSource` | Legacy RDBMS |
| `SnowflakeSource/Sink` | Snowflake shops |
| `UnityCatalogSource/Sink` | Databricks UC |

### 17.3 Config examples

```yaml
# sparkrules.yaml — local dev
runtime:
  profile: local
  executor: in_process
  fact_source:  { type: iceberg_like, catalog: file:///data/warehouse }
  result_sink:  { type: iceberg_like, catalog: file:///data/warehouse }
```

```yaml
# sparkrules.yaml — EMR prod
runtime:
  profile: emr
  executor: spark
  spark:
    master: yarn
    deploy_mode: cluster
    conf:
      spark.executor.instances: 50
      spark.executor.memory: 32g
      spark.sql.shuffle.partitions: 2000
  fact_source:
    type: iceberg
    catalog_impl: org.apache.iceberg.aws.glue.GlueCatalog
    warehouse: s3://retail-data/warehouse
  result_sink: { ... same catalog ... }
```

```yaml
# sparkrules.yaml — EKS Spark Connect
runtime:
  profile: eks_spark_connect
  executor: spark_connect
  spark_connect:
    endpoint: sc://spark-connect-server.sre.svc.cluster.local:15002
    tls: true
  fact_source:
    type: iceberg
    catalog_impl: org.apache.iceberg.rest.RESTCatalog
    uri: https://iceberg-catalog.internal
```

```yaml
# sparkrules.yaml — AWS Glue
runtime:
  profile: glue
  executor: glue
  glue:
    job_name: sparkrules-eod
    role_arn: arn:aws:iam::123:role/GlueSparkRules
    worker_type: G.2X
    number_of_workers: 20
    glue_version: "4.0"
  fact_source:
    type: iceberg
    catalog_impl: org.apache.iceberg.aws.glue.GlueCatalog
    warehouse: s3://retail-data/warehouse
```

```yaml
# sparkrules.yaml — Databricks
runtime:
  profile: databricks
  executor: databricks
  databricks:
    workspace_url: https://xyz.cloud.databricks.com
    cluster_id: 0101-abcd
    # or: warehouse_id: serverless
  fact_source:
    type: unity_catalog
    catalog: retail
    schema: pos
```

### 17.4 User-facing UX

Three ways to bind:

1. CLI: `sparkrules run --profile prod-emr --input pos_transactions`
2. Env var: `SPARKRULES_PROFILE=prod-emr`
3. REST body:
   ```json
   POST /runs
   { "profile": "prod-glue", "input_table_name": "pos_transactions" }
   ```

### 17.5 Backend-parity invariant

**P44: Backend-parity invariant** — ∀ rules R, facts F, backends
B1 B2 ∈ {in_process, spark, glue, databricks, ...},
`evaluate(B1, R, F) = evaluate(B2, R, F)` on `rule_results` fields excluding
`evaluated_ts` and `run_id`. Tested by running the same rule set and fact
multiset through every enabled backend in CI and asserting multiset equality.

### 17.6 Why this matters

- **Procurement answer:** "We don't lock you into a runtime. Run it on whatever Spark you already pay for."
- **Multi-cloud:** Same ruleset on Glue for batch, EKS Spark Connect for streaming, Databricks for simulation.
- **Dev → prod parity:** Developers run `profile: local`. CI runs `profile: local` with fixtures. Staging runs `profile: eks_spark_connect`. Prod runs `profile: emr` or `profile: glue`.


## 18. Phase 2c — AI-Assisted Rule Authoring

After the platform has run for N days, three kinds of data are captured:
fact samples per dataset, the existing rule catalog with DRL, and
`run_history` + `rule_results` + `dq_violations`. Combined, these let an LLM
propose new rules (business + DQ) that a human reviews and promotes.

### 18.1 Three AI features

**Feature 1 — Rule suggestion** ("Propose rules I don't have")

Pipeline:
1. Sample the Iceberg fact table (10k rows + schema).
2. Summarise distributions: null rates, min/max, cardinality, top values, timestamp ranges.
3. Summarise existing rule catalog: handles, reason codes, covered columns.
4. Compute "uncovered columns" = dataset columns × no existing rule references them.
5. Prompt the LLM with schema + stats + existing rules + the gap. Request 5-10 candidates.
6. LLM returns DRL drafts.
7. **Run each draft through `RuleSimulator`** against the last N days of facts.
8. Human reviews in the UI → promote or discard.

**Feature 2 — DQ rule mining** ("Propose DQ checks from observed behaviour")

Pipeline:
1. Profile last N days: null rate, uniqueness, value ranges, referential integrity.
2. Detect stable patterns: `null_rate < 0.1%` in 99% of days → `ExpectColumnValuesToBeNotNull`.
3. Detect stable ranges: `amount ∈ [0, 9999]` 100% of observations → `ExpectColumnValuesToBeBetween`.
4. Detect categorical closure: `country ∈ {US, CA, GB, FR}` always → `ExpectColumnValuesToBeInSet`.
5. Pass detected patterns + raw stats to LLM. Request DRL rules with `severity: WARN` and tolerance based on observed variance.
6. Simulator validates each against historical data; expected fire rate should be 0% on training window.
7. Human reviews, possibly adjusts, promotes.

**Feature 3 — Drift detection** ("This rule's behaviour is changing")

Pipeline:
1. Daily aggregate of fire rate, unique bound_field values, reason_code distribution.
2. Statistical change detection (CUSUM / Bayesian change-point).
3. On drift: prompt LLM with rule DRL + fire rate timeline + top bound_field values before/after.
4. LLM returns suggestions: add constraint, split rule, adjust threshold.
5. Suggestions go through existing A/B test infrastructure.

### 18.2 Pluggable LLM provider

```yaml
ai:
  enabled: true
  provider: bedrock
  bedrock:
    region: us-east-1
    model_id: anthropic.claude-sonnet-4-v1
    role_arn: arn:aws:iam::123:role/SparkRulesAI
  features:
    rule_suggestion: true
    dq_mining: true
    drift_detection: true
  safety:
    require_simulator_pass: true
    require_human_review: true
    max_suggestions_per_day: 20
    redact_pii_columns: [email, ssn, phone]
```

Provider abstraction:

```python
class AiProvider(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int) -> str: ...

class BedrockProvider(AiProvider): ...       # boto3 bedrock-runtime
class OpenAIProvider(AiProvider): ...
class AzureOpenAIProvider(AiProvider): ...
class VertexProvider(AiProvider): ...
class DatabricksFmProvider(AiProvider): ...
class LocalOllamaProvider(AiProvider): ...   # air-gapped deployments
```

### 18.3 Bedrock-specific positioning

- IAM role via IRSA (EKS) or instance profile (EMR).
- VPC endpoint for `bedrock-runtime` keeps traffic in-VPC — no egress.
- Model choice: Claude Sonnet for quality; Claude Haiku for cost-sensitive bulk profiling.
- Bedrock Guardrails for PII redaction at the provider level (defense in depth).
- CloudWatch logs every prompt + response (auditability).
- Bedrock Knowledge Bases optional — index rule catalog + DRL grammar doc for retrieval-grounded prompts.

This matters for regulated industries: OpenAI direct is often a non-starter
because data can't leave AWS. Bedrock stays within the customer's AWS account.

### 18.4 New API surface

```
POST /ai/suggest-rules
  body:    { dataset, window_days, max_suggestions }
  returns: [{ drl, reasoning, simulator_result, fire_rate, risk_score }, ...]

POST /ai/mine-dq-rules
  body:    { dataset, window_days }
  returns: [{ drl, severity, tolerance, observed_null_rate, simulator_result }, ...]

POST /ai/analyze-drift
  body:    { rule_handle, window_days }
  returns: { drift_detected, suggestions: [...] }

POST /ai/explain-rule
  body:    { rule_handle }
  returns: { natural_language_explanation, example_matches, reason_code_usage }

GET  /ai/suggestions                  # pending human review
POST /ai/suggestions/{id}/approve
POST /ai/suggestions/{id}/reject
```

### 18.5 Lifecycle of an AI suggestion

1. AI generates → stored as `is_active=false` with metadata tag `source: AI_SUGGESTION`.
2. Simulator scored → attached as `simulator_result` in the suggestion record.
3. Human approves via UI → promoted to active, overlap check, version assigned.
4. Optional: A/B test against current rule for N days before full rollout.

Every suggestion flows through the existing rule lifecycle — no bypass.

### 18.6 Safety + correctness guarantees

Reused from the existing test-verified infrastructure:

- **Simulator isolation (P24):** AI suggestions never persist until human approves.
- **Explanation sufficiency (P38):** AI-generated rules emit bound_fields that let an auditor understand the match without consulting the LLM.
- **Replay determinism (P36):** Suggestions validated by replaying real historical runs; if they would have over-fired, simulator shows it before promotion.
- **Overlap rejection (P3):** AI can't silently shadow an existing rule.

New AI-specific properties:

| # | Property |
|---|---|
| P45 | AI safety boundary — rule tagged `source: AI_SUGGESTION` is `is_active=false` until a human principal (≠ `ai_agent`) activates it. |
| P46 | Simulator evidence required — no AI suggestion is promoted to active without a linked `simulator_result` row. |
| P47 | PII redaction — fact samples sent to the LLM never contain values from `redact_pii_columns`. Test: ∀ LLM requests, payload field set is disjoint from configured PII column set. |

### 18.7 Why this is the feature that "sells"

Most vendors ship "LLM writes a rule from natural language" — a demo, not a
product. SparkRules' AI is different because every suggestion is:

- **Grounded in real data** — comes from customer's own historical runs.
- **Simulator-validated** — every suggestion has a replay score before a human sees it.
- **Explainable** — fired rule rows carry bound_fields, not just "AI said so".
- **Auditable** — every AI-generated rule carries `source: AI_SUGGESTION` + linked prompt/response in the audit log.
- **Pluggable provider** — Bedrock, OpenAI, Azure, Vertex, Databricks FM, or air-gapped Ollama.
- **Opt-in** — regulated customers can run the whole platform with `ai.enabled: false` and never touch an LLM.

Positioning line:
> "Self-improving rule platform on Spark. After 30 days of running, SparkRules proposes new business rules and data quality checks based on how your data actually behaves. Every suggestion is simulator-validated and human-reviewed before it goes live. Works with AWS Bedrock, OpenAI, Azure, Vertex, or your own model."


## 19. Consolidated Roadmap

```
Phase 1 — Core engine (DONE)
  - 25 tasks, 234 tests, 38 properties
  - POS EoD, auth streaming, settlement replay, underwriting integration tests
  - Reference Python implementation + Kubernetes manifests

Phase 2a — Data quality extension
  - severity / scope / tolerance / data_contract_id on Rule
  - Sugar primitives: ExpectColumnValuesToBeUnique, MatchRegex, etc.
  - data contracts (YAML)
  - DqRun + dq_violations Iceberg table + quarantine routing
  - Properties P39-P43

Phase 2b — Runtime profile extension
  - ExecutorBackend / FactSource / ResultSink protocols
  - Backends: InProcess, Spark (EMR/Dataproc/Synapse), SparkConnect (EKS/GKE), Glue, Databricks, EmrServerless
  - Sources/sinks: Iceberg, Delta, UnityCatalog, Kafka, Kinesis, Jdbc, Snowflake, Parquet
  - Property P44 (backend parity)

Phase 2c — AI-assisted rule authoring
  - AiProvider abstraction: Bedrock, OpenAI, Azure OpenAI, Vertex, Databricks FM, Ollama
  - Endpoints: /ai/suggest-rules, /ai/mine-dq-rules, /ai/analyze-drift, /ai/explain-rule, /ai/suggestions
  - Simulator-validated lifecycle for every suggestion
  - Properties P45-P47 (safety boundary, evidence required, PII redaction)

Phase 3 — Web UI (React + Monaco + AG Grid)
  - Rules list with enable/disable
  - DRL editor with parse-error highlighting
  - Decision table editor
  - XLSX upload
  - Simulator
  - Run history + replay
  - Version diff viewer
  - A/B test configurator
  - AI suggestions review queue

Phase 4 — Scala production port
  - sbt multi-module: engine-core, rule-api (Spring Boot), spark-connect-server
  - ANTLR4 grammar (Drl.g4) replaces hand-rolled Python parser
  - ScalaCheck ports every property test
  - Real Spark execution (PUSHDOWN, DATAFRAME, BROADCAST, SQL_JOIN)
  - Real Iceberg (pyiceberg or native)
  - Real Spark Connect gRPC
```

### 19.1 Phase dependencies

```
Phase 1 (done)
  |
  +-- Phase 2a (DQ) ----+
  |                     |
  +-- Phase 2b (Runtime)+--> Phase 3 (UI) --> Phase 4 (Scala port)
  |                     |
  +-- Phase 2c (AI) ----+
```

Phases 2a, 2b, 2c are independent and can ship in parallel. Phase 3 depends on
all three (UI surfaces DQ config, runtime profile selector, AI suggestion
queue). Phase 4 is the production path once the Python reference is
feature-complete.

### 19.2 Property coverage summary (projected)

| Phase | Properties added | Running total |
|---|---|---|
| Phase 1 (done) | P1-P38 | 38 |
| Phase 2a (DQ) | P39-P43 | 43 |
| Phase 2b (Runtime) | P44 | 44 |
| Phase 2c (AI) | P45-P47 | 47 |

Every property is universally quantified and machine-verified by Hypothesis
(Python) or ScalaCheck (Scala port), minimum 100 iterations.


## 20. Final Reference Commands

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

### Default test suite (Phase 1)

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q
# expected: 234 passed, 1 deselected
```

### Opt-in performance benchmark

```powershell
.\.venv\Scripts\python.exe -m pytest tests/perf -m perf -q
# expected: 1 passed
```

### Future (per-extension)

```powershell
# Phase 2a — DQ tests once added
.\.venv\Scripts\python.exe -m pytest tests/property/test_dq_properties.py -q

# Phase 2b — backend-parity test once added
.\.venv\Scripts\python.exe -m pytest tests/property/test_backend_parity.py -q

# Phase 2c — AI safety tests once added
.\.venv\Scripts\python.exe -m pytest tests/property/test_ai_safety.py -q
```


## 21. AI Code Generator Instructions

When rebuilding the full project including extensions:

1. Read `.kiro/specs/spark-rule-engine/{requirements,design,tasks}.md` — canonical Phase 1 spec.
2. Read this file — reproduction sequence + extension roadmap.
3. Execute Phase 1 reproduction per section 10 of this document (9 waves).
4. Validate: `234 passed, 1 deselected`.
5. For each Phase 2 extension, create `.kiro/specs/sparkrules-<extension>/` with requirements, design, tasks using the same EARS + correctness-property methodology.
6. Add new properties to the running total and verify with `pytest tests/ -q`.
7. Keep every component boundary stable — extensions plug in, do not fork.

When given only a short user prompt:

> "Build SparkRules."

The AI should:

1. Read `AI_REPRODUCTION_BLUEPRINT.md` (this file) first.
2. Read the three spec documents.
3. Implement Phase 1 verbatim (234 tests).
4. Ask the user which Phase 2 extensions to include before proceeding further.

---

**End of blueprint.**

Authoritative references in priority order:
1. `.kiro/specs/spark-rule-engine/requirements.md` — 34 requirements
2. `.kiro/specs/spark-rule-engine/design.md` — architecture + 38 properties
3. `.kiro/specs/spark-rule-engine/tasks.md` — 25-task plan
4. `AI_REPRODUCTION_BLUEPRINT.md` — reproduction + extensions (this file)
5. `BUILD_STATUS.md` — current engine state


## 22. Phase 2d — Graph-Enriched Fraud Rules

Fraud rings, collusion networks, synthetic identity clusters, and money-mule
trees are invisible to single-fact rules because the signal lives *between*
facts, not in any one fact. Graph enrichment turns "between" into "on"
so ordinary rules see the signal. Pattern validated by Uber Engineering's
published work on relational graph learning for collusion detection.
[Content rephrased from [Uber blog](https://www.uber.com/en-GB/blog/fraud-detection/).]

### 22.1 Design overview

A graph fraud signal is a *derived attribute* on a fact. Before a rule
evaluates a transaction, the fact is enriched with graph-computed features.
Once enriched, existing rules handle the new fields identically to any other
attribute.

Example rule over graph-derived fields:

```drl
rule "r_fraud_ring_hit"
    salience 100
    reason_codes ["FRAUD_RING_MATCH"]
when
    $a : Auth(
        cluster_risk_score > 0.3
        and n_hop_fraud_distance <= 2
        and shared_device_count > 5
    )
then
    result.decision = "decline";
end
```

No engine change needed. What changes is the enrichment pipeline upstream.

### 22.2 Three layers

**Layer 1 — Graph storage (pluggable backend)**

```python
class GraphSource(Protocol):
    def neighbours(self, node_id: str, hops: int) -> list[str]: ...
    def community(self, node_id: str) -> str: ...
    def centrality(self, node_id: str) -> float: ...
    def risk_score(self, node_id: str) -> float: ...
    def snapshot_id(self) -> int: ...
```

| Backend | Runtime |
|---|---|
| `NeptuneGraphSource` | AWS Neptune (Gremlin / OpenCypher) |
| `Neo4jGraphSource` | Neo4j |
| `TigerGraphSource` | TigerGraph |
| `JanusGraphSource` | JanusGraph over Cassandra |
| `SparkGraphFramesSource` | GraphFrames on Spark (batch-computed features) |
| `InMemoryGraphSource` | NetworkX for reference/tests |

**Layer 2 — Enrichment step**

`GraphEnricher` runs before the executor, writing graph-derived fields into
each fact dict. Two modes:

- **Precomputed** (batch): GraphFrames job writes features to an Iceberg
  table nightly; enricher joins by key. Cheap, stale up to 24 h.
- **Live query** (streaming): enricher calls Neptune/Neo4j per fact with a
  short TTL cache. Real-time signal, higher per-fact latency.

**Layer 3 — Graph-derived rule primitives (sugar)**

| Primitive | Expands to |
|---|---|
| `GraphRiskAbove(entity, threshold)` | `cluster_risk_score > threshold` |
| `NHopToKnownFraud(entity, hops)` | `n_hop_fraud_distance <= hops` |
| `SharedAttributeVelocity(attr, window, limit)` | combo over `shared_*` counts |
| `CommunityMembershipFlag(entity, flagged)` | `community IN (set)` |
| `CentralityAnomaly(entity, pct)` | `centrality > percentile(pct)` |

Author writes YAML:

```yaml
- id: r_fraud_ring_hit
  severity: CRITICAL
  primitive: GraphRiskAbove
  entity: account_id
  threshold: 0.3
```

Compiles to DRL; same compiler, executor, replay.

### 22.3 Config

```yaml
graph:
  enabled: true
  provider: neptune
  neptune:
    endpoint: wss://neptune.xyz.neptune.amazonaws.com:8182
    iam_auth: true
  enrichment_mode: live_query        # or: precomputed
  precomputed_table: s3://fraud-features/graph_features
  cache_ttl_seconds: 30
  features:
    - cluster_risk_score
    - n_hop_fraud_distance
    - shared_device_count
    - community_id
  pii_redaction:
    hash_node_ids: true
    salt_source: secret:sre-graph-salt
```

### 22.4 Replay semantics

`GraphSource.snapshot_id()` becomes part of `config_fingerprint`. Replay
reads the exact graph snapshot that the original run used. P36 extends
naturally — a replay is byte-equal across graph + fact snapshots together.

### 22.5 New correctness properties

| # | Property |
|---|---|
| P48 | Graph snapshot determinism — same `(graph_snapshot_id, fact_snapshot_id, rule_set_version)` yields multiset-equal `rule_results`. |
| P49 | Enrichment idempotency — re-enriching an already-enriched fact produces the same dict. |
| P50 | Graph primitive expansion equivalence — sugar AST evaluates to the same fired set as the hand-written equivalent DRL. |
| P51 | PII-aware graph redaction — node ids in `bound_fields` are pseudonymous tokens unless caller has `pii_reveal` role. |

### 22.6 Why this matters for positioning

- Standalone rule engines cannot express fraud ring detection.
- Closed-source commercial systems (FICO, IBM ODM) do, at per-seat licensing.
- Graph databases on their own have no rule authoring UX.
- SparkRules + graph enricher covers the full path: ring detection as a rule
  a business analyst can author, version, and replay.


## 23. Phase 2e — ML Model Scoring as a Rule Action

Rule engines and ML models are usually deployed separately with duplicate
feature pipelines and no shared audit trail. SparkRules can host both under
one catalog: a rule invokes a model, the model returns a score, the score
feeds another rule or a threshold, the decision is emitted with
bound_fields that include the model id and score.

### 23.1 Design

Add a `ModelInvoker` primitive usable in rule actions:

```drl
rule "r_ml_risk_step_up"
    reason_codes ["ML_RISK_HIGH"]
when
    $a : Auth(amount > 100)
then
    risk_score = invoke_model("auth_fraud_v3", $a);
    result.ml_score = risk_score;
    if (risk_score > 0.8) result.decision = "step_up";
end
```

### 23.2 Pluggable model providers

```python
class ModelProvider(Protocol):
    def score(self, model_id: str, features: dict) -> dict: ...
    def model_version(self, model_id: str) -> str: ...
```

Concrete backends:

| Backend | Runtime |
|---|---|
| `SageMakerEndpointProvider` | AWS SageMaker real-time endpoint |
| `BedrockModelProvider` | Bedrock hosted classifier |
| `MlflowModelProvider` | MLflow model serving |
| `TritonModelProvider` | NVIDIA Triton |
| `DatabricksModelServingProvider` | Databricks model serving |
| `LocalOnnxProvider` | Local ONNX runtime (air-gapped) |

### 23.3 Feature assembly from bound fields

The model call is fed by `bound_fields` from the matched pattern. That keeps
explanation sufficiency (P38) intact — the same bound_fields that explain
the rule also explain the model call.

### 23.4 Replay semantics

Every run records `(model_id, model_version)` per rule invocation. Replay
pins the model version. When a model is retrained, replay still uses the
version live at the original run — unless the caller explicitly asks to
replay against the current version (for regression comparison).

### 23.5 New correctness properties

| # | Property |
|---|---|
| P52 | Model version pinning — replay uses the model version recorded on the original run. |
| P53 | Model score determinism (pinned version) — same `(model_id, version, features)` yields the same score. |
| P54 | Score explanation — every fired rule whose action invoked a model emits `{model_id, model_version, features, score}` in `action_output`. |

### 23.6 Positioning

"Author rules AND ML-scored decisions in the same DRL catalog. Every auth,
every application, every settlement carries the exact model version and
score that drove its decision, replayable months later for any regulator."

## 24. Phase 2f — Data Lineage and Governance

Regulated shops need evidence of data provenance end-to-end. SparkRules
already records `run_history` with snapshot ids and rule set versions; this
phase formalises the lineage emission.

### 24.1 OpenLineage integration

Every run emits OpenLineage events:

- `START` event: inputs (Iceberg tables + snapshot ids), rule set version,
  config fingerprint, profile.
- `COMPLETE` event: outputs (rule_results, run_history, dq_violations),
  metrics (facts_processed, rules_fired, violations_by_severity).
- `FAIL` event on error with exception class + message.

### 24.2 DataHub / Unity Catalog / Atlas adapters

```python
class LineageSink(Protocol):
    def emit(self, event: dict) -> None: ...

class OpenLineageSink(LineageSink): ...          # Marquez, DataHub, OpenLineage-native
class DataHubSink(LineageSink): ...              # Acryl DataHub
class UnityCatalogLineageSink(LineageSink): ...  # Databricks UC
class AtlasSink(LineageSink): ...                # Apache Atlas / AWS Glue
```

### 24.3 Rule-level lineage

Every `rule_results` row links to:
- Input `(table, snapshot_id)` via run_history.
- `rule_handle`, `version`, `rule_set_version`.
- `author_principal`, `created_at` (audit log).
- If the rule came from an AI suggestion: the suggestion id, prompt hash,
  model id/version, human approver.
- If the rule used graph enrichment: `(graph_snapshot_id, enriched_features)`.
- If the rule invoked a model: `(model_id, model_version, features)`.

Lineage queries become trivial: "show every decision that used rule
`r_fraud_ring_hit@version=7` between March 1 and April 30" is a single SQL
query over `rule_results` + `run_history`.

### 24.4 New properties

| # | Property |
|---|---|
| P55 | Lineage completeness — ∀ run_id in run_history, exactly one START and one COMPLETE/FAIL event. |
| P56 | Audit chain integrity — every active rule's version history is reconstructible from audit_log + rules table with no gaps. |

## 25. Phase 2g — Multi-Tenancy, SSO, and RBAC

Already partially accounted for in the design (`X-Principal` header). This
phase formalises enterprise identity.

### 25.1 Tenant isolation

- Each tenant maps to a separate Iceberg namespace.
- Rules, runs, rule_results, dq_violations, suggestions all scoped to tenant.
- Metrics labelled with `tenant_id`.
- ConnectServer sessions per-tenant with tenant-scoped catalog credentials.

### 25.2 AuthN providers

- OIDC (generic): Okta, Auth0, Azure AD, Google Workspace, Keycloak.
- SAML 2.0 for legacy enterprise.
- mTLS for service-to-service (executors ↔ Iceberg catalog, Connect ↔ gRPC).
- AWS IAM via IRSA on EKS or instance profile on EMR.

### 25.3 RBAC roles

| Role | Permissions |
|---|---|
| `rule_reader` | `GET /rules`, `GET /runs`, `GET /decision-tables` |
| `rule_author` | reader + `POST`/`PUT` rules, import, simulate |
| `rule_admin` | author + `DELETE`, activate, A/B test create |
| `run_operator` | `POST /runs`, replay, run metrics |
| `dq_steward` | manage data contracts, view violations |
| `ai_reviewer` | approve/reject AI suggestions |
| `pii_reveal` | unmask redacted values in bound_fields |
| `platform_admin` | full access, Catalyst config, quota overrides |

### 25.4 Audit log

Append-only Iceberg table `audit_log` with
`(ts, principal, action, resource, request_hash, response_status, tenant_id)`.
Every mutating API call records one row. Read-only endpoints optionally
logged behind a flag for high-compliance tenants.

### 25.5 New properties

| # | Property |
|---|---|
| P57 | Tenant isolation — ∀ requests, response rows are a subset of the caller's tenant namespace. |
| P58 | RBAC enforcement — a principal without role R cannot invoke any endpoint requiring R; returns 403. |
| P59 | Audit log append-only — no UPDATE or DELETE succeeds against audit_log (Iceberg row-level deletes disabled on this table). |

## 26. Phase 2h — Developer Experience and Operational Tooling

Features that lower adoption friction, not strictly part of the engine.

### 26.1 CLI

```
sparkrules rules list        [--group <g>] [--active] [--format yaml|json]
sparkrules rules get         <handle> [--version <n>]
sparkrules rules create      --file rule.drl [--principal <name>]
sparkrules rules activate    <handle> --version <n>
sparkrules rules disable     <handle>
sparkrules rules diff        <handle> --from <v1> --to <v2>
sparkrules rules simulate    --file draft.drl --sample sample.json

sparkrules runs submit       --profile <name> --input <table> [--snapshot <id>]
sparkrules runs list         [--status SUCCESS|FAILED] [--mode BATCH|STREAMING]
sparkrules runs get          <run_id> [--include-metrics]
sparkrules runs replay       <run_id>

sparkrules dt import         --file rules.xlsx
sparkrules dt export         --handle <h> --output rules.xlsx

sparkrules ai suggest        --dataset <name> --window-days 30
sparkrules ai approve        <suggestion_id>
sparkrules ai reject         <suggestion_id>

sparkrules dq contract apply --file contract.yaml
sparkrules dq violations     --run <run_id> --severity CRITICAL

sparkrules graph features    --dataset <name>
sparkrules graph enrich      --fact-id <id>

sparkrules profile list
sparkrules profile use       <name>

sparkrules serve             --port 8080        # starts REST
sparkrules connect           --port 15002       # starts ConnectServer
```

Exit codes stable per operation for CI integration.

### 26.2 IDE support

- VS Code extension for DRL syntax highlighting + parse error diagnostics.
- Language Server Protocol for rule_handle autocomplete, version navigation.
- Snippets for common rule patterns (threshold, decision table, Pass_2 quota).

### 26.3 Rule testing framework

Per-rule unit tests in a declarative format:

```yaml
rule: r_fraud_ring_hit
scenarios:
  - name: "fires on high cluster risk"
    fact: { account_id: a1, cluster_risk_score: 0.5, n_hop_fraud_distance: 1, shared_device_count: 10 }
    expected: { fired: true, decision: "decline" }
  - name: "does not fire below threshold"
    fact: { account_id: a2, cluster_risk_score: 0.1, n_hop_fraud_distance: 5, shared_device_count: 2 }
    expected: { fired: false }
```

`sparkrules rules test r_fraud_ring_hit` runs all scenarios via the simulator.

### 26.4 Chaos and failure injection for tests

Under `tests/chaos/` — injects random failures into the executor, broadcast
assembler, and Iceberg sink to validate the existing exception-isolation and
retry invariants (P27, P23) at integration scale.

### 26.5 SDK bindings beyond Python

- Java/Kotlin client (thin gRPC/HTTP wrapper) for JVM apps.
- Go client for infra tooling.
- TypeScript client generated from OpenAPI schema (feeds the web UI).

## 27. Phase 2i — Additional Strategic Extensions

Shortlist of "what else" ideas worth considering, each single-paragraph.

### 27.1 Natural-language rule authoring

Layer on top of Phase 2c AI. Business user writes "when a customer's spend
this month is over $500 and they're Gold tier, apply a 5% discount" — LLM
converts to DRL, simulator validates, human approves. Not a replacement for
the structured editor, a convenience for power users.

### 27.2 Rule coverage analysis

Static analysis of the rule catalog to report dead rules (never fire on
recent data), overlapping rules (two rules match the same fact shape), and
coverage gaps (facts matched by no rule). Daily job, surfaced in the UI.

### 27.3 Rule deprecation workflow

Mark rules as `deprecated=true`, fires with a `DEPRECATED_RULE_*` reason code,
triggers a scheduled job to clean up after N days of zero firings.

### 27.4 Shadow mode / canary deployment

Activate a rule in `shadow=true` — it runs, emits `rule_results`, but its
`action_output` is tagged SHADOW and not forwarded to downstream consumers.
Compare shadow outcomes against production for a week before full activation.

### 27.5 Time-travel debugger for rules

Given a fact id and a run id, reconstruct the exact rule evaluation path: DN
walk, agenda ordering, activation-group resolution, action execution, with
intermediate values at each node. Powerful for debugging "why didn't my rule
fire on this transaction?"

### 27.6 Counter-factual analysis

Given a past run, answer: "what would rule_results have been if rule X had
been active that day?" Implemented as a replay with a modified rule set.

### 27.7 Decision-table synthesis from examples

User uploads a CSV of (input_cols, expected_output). Engine synthesises a
minimal decision table (via ID3-style induction) that reproduces every row.
Combine with AI assist for cleanup and hit-policy selection.

### 27.8 Multi-region replication

`RuleMetadataStore` replication across regions with CRDT semantics on
version numbers. Enables active-active deployments for multi-region payment
networks.

### 27.9 Marketplace

Publish/share common rule packs: PCI-DSS validation, GDPR data contracts,
Basel III risk rules, common fraud primitives. Importable into a tenant
namespace as a starting point.

### 27.10 SOC 2 / PCI-DSS preset configurations

Opinionated configs that turn on audit log, require PII redaction, enforce
RBAC, disable AI suggestion auto-approve. One flag to apply.


## 28. Updated Consolidated Roadmap

```
Phase 1 — Core engine                          (DONE: 234 tests, P1-P38)
  |
  +-- Phase 2a — Data quality              (P39-P43)
  +-- Phase 2b — Runtime profiles          (P44)
  +-- Phase 2c — AI-assisted authoring     (P45-P47)
  +-- Phase 2d — Graph-enriched fraud      (P48-P51)
  +-- Phase 2e — ML model scoring          (P52-P54)
  +-- Phase 2f — Lineage and governance    (P55-P56)
  +-- Phase 2g — Multi-tenancy + RBAC      (P57-P59)
  +-- Phase 2h — Developer UX              (no new P)
  +-- Phase 2i — Strategic add-ons         (no new P, case-by-case)
  |
  +-- Phase 3 — Web UI
  |
  +-- Phase 4 — Scala production port
```

### 28.1 Independence matrix

| Phase | Blocks | Blocked by |
|---|---|---|
| 2a DQ | — | 1 |
| 2b Runtime | — | 1 |
| 2c AI | benefits from 2a + 2d | 1 |
| 2d Graph | — | 1 |
| 2e ML | — | 1 |
| 2f Lineage | — | 1 |
| 2g RBAC | — | 1 |
| 2h Dev UX | — | 1 |
| 2i Add-ons | case-by-case | 1 |
| 3 UI | full stack | 2a, 2b, 2c |
| 4 Scala | production | 1 (can parallel with 2x) |

All Phase 2 streams can ship in parallel. Phase 3 depends on at least one
Phase 2 stream being visible in the UI (typically 2a or 2c). Phase 4 is
independent of Phase 2 but benefits from settled Phase 2 APIs.

### 28.2 Property coverage projection

| Phase | Properties added | Running total |
|---|---|---|
| 1 (done) | P1-P38 | 38 |
| 2a DQ | P39-P43 | 43 |
| 2b Runtime | P44 | 44 |
| 2c AI | P45-P47 | 47 |
| 2d Graph | P48-P51 | 51 |
| 2e ML | P52-P54 | 54 |
| 2f Lineage | P55-P56 | 56 |
| 2g RBAC | P57-P59 | 59 |

Every property is universally quantified, machine-verified by Hypothesis
(Python) or ScalaCheck (Scala port), minimum 100 iterations.

## 29. Revised AI Code Generator Instructions

When given only a short user prompt:

> "Build SparkRules."

The AI should:

1. Read `AI_REPRODUCTION_BLUEPRINT.md` (this file) first.
2. Read the three canonical specs:
   - `.kiro/specs/spark-rule-engine/requirements.md`
   - `.kiro/specs/spark-rule-engine/design.md`
   - `.kiro/specs/spark-rule-engine/tasks.md`
3. Implement Phase 1 verbatim (234 tests, 38 properties).
4. Ask the user which Phase 2 extensions to include:
   - 2a Data quality
   - 2b Runtime profiles (EMR / Glue / EKS / Databricks / Dataproc)
   - 2c AI assist (Bedrock / OpenAI / Azure / Vertex / Databricks FM / Ollama)
   - 2d Graph fraud (Neptune / Neo4j / TigerGraph / GraphFrames)
   - 2e ML scoring (SageMaker / Bedrock / MLflow / Triton / Databricks)
   - 2f Lineage (OpenLineage / DataHub / Unity Catalog / Atlas)
   - 2g RBAC + SSO (OIDC / SAML / IAM)
   - 2h Dev UX (CLI / IDE / SDK / chaos tests)
5. For each selected Phase 2 stream, create a sub-spec under
   `.kiro/specs/sparkrules-<extension>/` with requirements, design, tasks
   following the same EARS + correctness-property methodology as Phase 1.
6. Implement one Phase 2 stream at a time; run `pytest tests/ -q` after each.
7. Phase 3 (UI) only after at least one Phase 2 stream is complete.
8. Phase 4 (Scala port) as an independent track.

Never fork the engine. Extensions plug in through the existing abstractions
(`RuleMetadataStore`, `RuleCompiler`, `RuleExecutor`, `BatchEvaluator`,
`StreamingEvaluator`, `ReplayService`, `Simulator`).

---

**End of blueprint (v2).**

**Summary of authoritative references:**

| File | Purpose |
|---|---|
| `.kiro/specs/spark-rule-engine/requirements.md` | 34 EARS requirements (Phase 1) |
| `.kiro/specs/spark-rule-engine/design.md` | Architecture + 38 properties (Phase 1) |
| `.kiro/specs/spark-rule-engine/tasks.md` | 25-task implementation plan (Phase 1) |
| `AI_REPRODUCTION_BLUEPRINT.md` | This file — reproduction + Phase 2 extensions |
| `USE_CASES.md` | Five real-world domain catalogues + execution-control feature map |
| `BUILD_STATUS.md` | Current engine state |

Phase 2 extension specs (to be created as streams are picked up):

| Planned path | Coverage |
|---|---|
| `.kiro/specs/sparkrules-data-quality/` | Phase 2a |
| `.kiro/specs/sparkrules-runtime-profiles/` | Phase 2b |
| `.kiro/specs/sparkrules-ai-assist/` | Phase 2c |
| `.kiro/specs/sparkrules-graph-fraud/` | Phase 2d |
| `.kiro/specs/sparkrules-ml-scoring/` | Phase 2e |
| `.kiro/specs/sparkrules-lineage/` | Phase 2f |
| `.kiro/specs/sparkrules-rbac/` | Phase 2g |
| `.kiro/specs/sparkrules-devux/` | Phase 2h |
| `.kiro/specs/sparkrules-ui/` | Phase 3 |
| `.kiro/specs/sparkrules-scala-port/` | Phase 4 |


## 30. Phase 2j — dbt Integration

dbt is the de-facto tool for shaping raw sources into clean fact tables. It
is **not** a rule engine and should not be used as one. SparkRules fits
downstream of dbt in a standard modern data stack:

```
Raw sources (CSV / JSON / Kafka / RDBMS)
   |
   v
dbt models:  staging -> intermediate -> mart.pos_transactions (Iceberg)
   |
   v
SparkRules reads mart.pos_transactions at snapshot S0
   |
   v
rule_results + run_history + dq_violations
   |
   v
Downstream consumers (BI, ML, services)
```

Clean split of responsibilities:

| Tool | Owns |
|---|---|
| dbt | Shape and materialise fact tables, simple column-level tests |
| SparkRules | Business rules, complex DQ, two-pass quotas, replay, audit |
| Airflow / Dagster / Databricks Workflows | Orchestrate dbt then SparkRules |

### 30.1 dbt tests vs SparkRules DQ

- **dbt tests** — "Is this column shaped right?" (not_null, unique, accepted_values, relationships). Schema-level DQ.
- **SparkRules DQ** — "Is this record a valid business transaction?" Cross-fact reconciliation, multi-column invariants, two-pass aggregate checks, quarantine routing, reason codes, replay.

Run dbt tests as a pre-flight gate. Run SparkRules for the complex business DQ.

### 30.2 Integration deliverables

1. **`DbtFactSource` adapter** — resolves a dbt model reference (`mart.pos_transactions`) to its Iceberg location via `manifest.json`. Records the manifest hash in `config_fingerprint` for replay pinning.
2. **dbt package `sparkrules_dbt`** — macros exposing `rule_results`, `run_history`, `dq_violations` as dbt sources; optional post-hook to trigger a SparkRules run after a dbt model materialises.
3. **OpenLineage + dbt node linkage** — SparkRules runs emit lineage events that reference the upstream dbt node IDs.

### 30.3 Config example

```yaml
fact_source:
  type: dbt
  dbt_project_dir: /workspace/dbt/retail
  manifest_path: /workspace/dbt/retail/target/manifest.json
  model: mart.pos_transactions
  pin_manifest_hash: true   # adds manifest hash to config_fingerprint
```

### 30.4 New property

| # | Property |
|---|---|
| P60 | dbt manifest pinning — a run whose `config_fingerprint` includes a dbt manifest hash replays against the same manifest, producing multiset-equal `rule_results`. |

### 30.5 Positioning

"SparkRules fits a modern data stack: dbt shapes facts, SparkRules evaluates
business rules + DQ, Airflow orchestrates the sequence. Lineage flows through
OpenLineage into DataHub or Unity Catalog. Every decision is replayable to
the dbt manifest hash that produced its input snapshot."


## 31. Prior Art and Competitive Landscape

Verified references to existing work. SparkRules differentiates by combining
capabilities none of these combine under one catalog.

### 31.1 Research

- **Park et al. 2017 — "When Rule Engine Meets Big Data"** ([IEEE 7944919](https://ieeexplore.ieee.org/document/7944919))
  Academic prototype for IoT edge rule engines over Spark. Rete-like on Spark for IoT event/action deployment. Validates the broadcast-based execution model. No production maintainers, no authoring UX, no versioning, no replay, no decision tables. Content rephrased from [ResearchGate abstract](https://www.researchgate.net/publication/317558467).

- **KSSRE 2018 — "A Distributed Rule Engine for Streaming Big Data"** ([Springer](https://link.springer.com/chapter/10.1007/978-3-030-02934-0_12))
  Kafka + Spark Structured Streaming rule engine research. Ternary-grid rule representation. No production fork.

### 31.2 Open-source projects

- **[databrickslabs/dataframe-rules-engine](https://github.com/databrickslabs/dataframe-rules-engine)** (Scala, archived-in-practice)
  Databricks Labs data-validation library. Four rule types (Simple, Boundary, Implicit Boolean, Categorical). README explicitly positions it as a stopgap: "Databricks recognizes this and, as such, is building Delta Pipelines with Expectations. Upon release of Delta Pipelines, the need for this package will be re-evaluated." Content rephrased for licensing compliance.

- **[apache/incubator-kie-drools](https://github.com/apache/incubator-kie-drools)** (Java, active)
  The canonical rule engine. Single-JVM; no native Spark / Iceberg / snapshot replay. We preserve its authoring semantics.

- **[HACEP](https://github.com/redhat-italy/hacep)** (Red Hat, abandoned)
  Distributed Drools CEP on Infinispan. Closest historical attempt at "distributed Drools." No longer maintained.

- **Small community repos** (cpitman/spark-drools-example, reynoldsm88/spark-drools, reethified/spark-drools)
  README-level tutorials, <50 stars each. [Content rephrased.]

- **Bad Apples / radanalytics.io** ([overview](https://radanalytics.io/applications/bad-apples))
  Red Hat-adjacent Spark + Drools fraud detection tutorial. Pattern demo, not a product.

### 31.3 Closed-source commercial

- **Delta Live Tables Expectations** — Databricks-only, closed-source, tied to DLT pipeline runtime. No Drools parity.
- **FICO Blaze Advisor** — closed-source, per-core licensing, not Spark-native.
- **IBM Operational Decision Manager (ODM)** — same class as FICO.
- **Pega** — BPM + rules, not Spark-native.
- **SAS Business Rules Manager** — enterprise, closed-source.

### 31.4 Feature matrix — SparkRules vs prior art

| Capability | Park 2017 | Databricks Labs | DLT Expectations | Drools | FICO Blaze | SparkRules |
|---|---|---|---|---|---|---|
| DRL-equivalent syntax | No | No | No | Yes | Proprietary | Yes |
| Salience / agenda / activation groups | No | No | No | Yes | Yes | Yes |
| Decision tables + XLSX import | No | No | No | Yes | Yes | Yes |
| Forward / backward chaining | Partial | No | No | Yes | Yes | Yes |
| Versioned rule catalog | No | No | Git-coupled | External | Yes | Yes |
| Effective dates + soft delete | No | No | No | No | Yes | Yes |
| Overlap rejection | No | No | No | No | No | Yes (P3) |
| Rule simulator (non-persistent) | No | No | No | Partial | Yes | Yes (P24) |
| A/B testing | No | No | No | No | Yes | Yes (P25) |
| Two-pass quota rules (first-class) | No | Partial | No | No | No | Yes (P28/29) |
| Hybrid execution (pushdown/DF/broadcast/SQL join) | No | DataFrame only | DataFrame only | n/a | n/a | Yes (P17) |
| Discrimination network (shared sub-predicate) | Rete-ish | No | No | Yes (Rete) | Yes | Yes (P19/20) |
| Rule batching with equivalence | No | No | No | No | No | Yes (P18) |
| Dynamic rule reload mid-stream | No | No | Pipeline restart | KieScanner (JVM) | Yes | Yes (P23) |
| Snapshot-pinned replay (Iceberg time travel) | No | No | No | No | No | Yes (P36) |
| Explanation sufficiency (bound_fields re-evaluable) | No | No | No | Partial | Yes | Yes (P38) |
| Mode parity (batch = streaming) | No | Partial | No | No | No | Yes (P33) |
| Per-rule per-fact exception isolation | No | No | No | Partial | Yes | Yes (P27) |
| Property-based verification | No | No | No | No | No | Yes (38+ properties) |
| REST API + Python SDK | No | No | Databricks-only | JBoss API | Vendor SDK | Yes |
| Runtime-agnostic (EMR/Glue/EKS/Databricks/Dataproc) | Spark only | Spark only | Databricks only | n/a | Appliance | Yes (Phase 2b) |
| Graph-enriched fraud rules | No | No | No | No | Yes | Phase 2d |
| AI-assisted authoring grounded in real runs | No | No | No | No | Partial | Phase 2c |
| Open source | Paper only | Archived-in-practice | Proprietary | Yes (Apache) | Proprietary | Planned |

### 31.5 Conclusion

In a decade of research and community effort, nobody shipped a production
open-source product that combines Drools authoring + Spark scale +
snapshot-pinned replay + property-verified correctness. The required
expertise sits at the intersection of two rarely-overlapping skill sets
(rule engines + Spark internals), and the incentive structure of both the
Drools (Apache KIE) and Databricks ecosystems works against building it.
This is the gap SparkRules fills.


## 32. Storage Backend Strategy (Requirements 35-40)

The blueprint now has formal requirements for pluggable storage. This
section tells an AI code generator how to honour them.

### 32.1 Rule metadata store — four backends behind one protocol

```python
class RuleMetadataStore(Protocol):
    def insert(self, rule: Rule) -> Rule: ...
    def update(self, rule_handle: str, patch: Rule) -> Rule: ...
    def soft_delete(self, rule_handle: str) -> list[Rule]: ...
    def activate(self, rule_handle: str, version: int) -> Rule: ...
    def get(self, rule_handle: str, version: int) -> Rule: ...
    def resolve(self, rule_handle: str, t: datetime) -> Rule | None: ...
    def list(self, f: RuleFilter | None) -> list[Rule]: ...
    def list_versions(self, rule_handle: str) -> list[Rule]: ...
    def active_set_version(self, t: datetime) -> str: ...
```

Four implementations, each in its own module under `src/sre/store/`:

| Module | Backend | When to use |
|---|---|---|
| `memory.py` | `InMemoryStore` | Unit tests, transient runs (Phase 1, built) |
| `duckdb.py` | `DuckDBStore` | Laptop dev, CI fixtures, demos (Phase 1.1) |
| `iceberg.py` | `IcebergStore` | Production multi-writer with time travel (Phase 2b) |
| `postgres.py` | `PostgresStore` | OLTP-centric shops (optional) |

Selection via config:

```yaml
store:
  backend: iceberg   # or: in_memory | duckdb | postgres
  iceberg:
    catalog_impl: org.apache.iceberg.rest.RESTCatalog
    uri: https://iceberg-catalog.internal
    namespace: sparkrules
  duckdb:
    path: ./sparkrules.duckdb
  postgres:
    url: postgresql://user:pw@host/sparkrules
```

### 32.2 Store-parity invariant (new property)

| # | Property |
|---|---|
| P67 | Store parity — ∀ backends B1 B2 and ∀ rule-store operation sequences Ops, the observable behaviour of `Ops` on B1 equals `Ops` on B2. Every property test for the store (P1, P2, P3, P5) runs against every backend in CI. |

### 32.3 Output table format — pluggable

```yaml
result_sink:
  format: iceberg   # or: delta | hudi | parquet
  iceberg:
    catalog_impl: org.apache.iceberg.aws.glue.GlueCatalog
    warehouse: s3://sparkrules/results
  delta:
    path: s3://sparkrules/results
  parquet:
    path: s3://sparkrules/results
```

Row-level deletes required for Iceberg / Delta / Hudi (chargeback
amendments). Parquet rejects replay if amendments exist (Requirement 36.5).

### 32.4 Input fact source — seven formats, one contract

| Format | Production-ready | Snapshot support |
|---|---|---|
| Iceberg | Yes | Native snapshot_id |
| Delta Lake | Yes | Native version |
| Apache Hudi | Yes | Native instant |
| Parquet (bare) | Read-only legacy | File-list hash surrogate |
| ORC | Yes | Native |
| Avro on Kafka | Streaming | Offset |
| Protobuf on Kafka | Streaming | Offset |
| JSON / JSONL | Ingestion only | None, warning emitted |
| CSV | Dev only | None, warning emitted |

Contract: every Fact carries a `fact_id_field`, every referenced rule field
exists in the source schema, streaming sources declare a watermark and
partition key.

### 32.5 DuckDB as analyst read path

DuckDB is the recommended interactive query engine for the Iceberg-backed
result tables. Document this in `TUTORIAL.md` so analysts know:

```sql
-- DuckDB reading Iceberg parquet files directly
SELECT rule_handle, COUNT(*) AS fires
FROM read_parquet('s3://sparkrules/results/rule_results/**/*.parquet')
WHERE evaluated_ts >= now() - INTERVAL 7 DAYS
GROUP BY rule_handle
ORDER BY fires DESC;
```

No engine change — DuckDB just reads the files the engine writes.

## 33. User-Defined Function Registry (Requirement 42)

Closes the last zero-code-change gap. Business or platform users register
functions by name and version; rules reference them by name.

```python
class UdfRegistry(Protocol):
    def register(self, fn: UdfSpec) -> UdfSpec: ...
    def resolve(self, name: str, at: datetime) -> UdfSpec | None: ...
    def list(self, f: UdfFilter | None) -> list[UdfSpec]: ...
```

```python
@dataclass(frozen=True, slots=True)
class UdfSpec:
    udf_id: UUID
    name: str
    version: int
    signature: tuple[type, ...]
    return_type: type
    purity: Literal["pure", "impure"]
    body: str                # Python source OR "pkg.module:callable"
    body_kind: Literal["source", "import_path"]
    effective_from: datetime
    effective_to: datetime | None
    author_principal: str
    created_at: datetime
```

DRL becomes:

```drl
rule "airline_fuzzy_match"
when
    $p : Person(jaro_winkler($p.name, $existing.name) > 0.92)
then
    result.link = true;
end
```

### 33.1 UDF correctness properties

| # | Property |
|---|---|
| P68 | UDF determinism (pure) — ∀ pure UDF F and inputs X, F(X) == F(X) across invocations. |
| P69 | UDF replay pinning — a replay resolves UDFs to versions effective at the original run's timestamp, not the current versions. |
| P70 | UDF sandbox — impure UDFs exceeding the per-call timeout are cancelled; their exception is isolated per fact (composes with P27). |

### 33.2 Built-in UDF library

Phase 2m-bis: ship a set of common domain UDFs as pre-registered built-ins
so users don't write them:

- String similarity: `jaro_winkler`, `levenshtein`, `soundex`, `metaphone`.
- Geo: `haversine_distance`, `point_in_polygon`.
- Checksums: `luhn`, `iban_checksum`, `isbn_checksum`.
- Date math: `business_days_between`, `age_years`.
- Crypto hashing: `sha256_hex`, `hmac_sha256`.

Users opt in per tenant. Register-once, use-from-any-rule.

## 34. Revised AI Code Generator Instructions (final)

When given a short user prompt like "Build SparkRules":

1. **Read `AI_REPRODUCTION_BLUEPRINT.md` in full** (this file).
2. **Read the three canonical specs** referenced at §14 of this file.
3. **Read `USE_CASES.md`** for concrete domain semantics.
4. **Read `ARCHITECTURE.md`** for system context diagrams.
5. **Implement Phase 1 per §10** (9 waves, 25 tasks, 38 properties).
6. After Phase 1 green (`234 passed, 1 deselected`), **ask the user which Phase 2 streams to implement** by presenting this table:

   | Phase | Theme | Enables |
   |---|---|---|
   | 1.1 | DuckDB store | Laptop dev, CI fixtures |
   | 2a | Data quality | Severity, scope, contracts, dq_violations |
   | 2b | Runtime profiles | EMR / Glue / EKS / Databricks / Dataproc |
   | 2c | AI assist | Bedrock / OpenAI / Azure / Vertex / Databricks FM / Ollama |
   | 2d | Graph fraud | Neptune / Neo4j / TigerGraph / GraphFrames |
   | 2e | ML model scoring | SageMaker / Bedrock / MLflow / Triton |
   | 2f | Lineage | OpenLineage / DataHub / Unity / Atlas |
   | 2g | RBAC + SSO | OIDC / SAML / IAM |
   | 2h | Developer UX | CLI / IDE / SDK |
   | 2j | dbt integration | Manifest pinning |
   | 2k | Execution policy | Fail-fast, first-failure, stop_on_fire |
   | 2m | UDF registry | Custom functions in DRL |
   | 2n | Output format | Delta / Hudi / Parquet sinks |
   | 3 | Web UI | React + Monaco + AG Grid |
   | 4 | Scala port | Production JVM path |

7. For each selected Phase 2 stream, create a sub-spec under
   `.kiro/specs/sparkrules-<extension>/` with requirements, design, tasks
   using the same EARS + correctness-property methodology as Phase 1.
8. Implement one Phase 2 stream at a time; run `pytest tests/ -q` after each.
9. Never fork the engine. Extensions plug in through the existing protocols
   (`RuleMetadataStore`, `ExecutorBackend`, `FactSource`, `ResultSink`,
   `GraphSource`, `ModelProvider`, `AiProvider`, `LineageSink`,
   `UdfRegistry`).
10. Respect the zero-code-change contract (Requirement 41): authoring
    surfaces + configuration never require code changes at use time.

### 34.1 Hard rules for the code agent

- **Never** embed tenant-specific logic in the engine. Everything tenant-specific lives in the rule catalog, the UDF registry, the config, or the data contract.
- **Always** pair an implementation task with a test (example or property).
- **Always** extend property coverage when adding a new extension (P39-P70).
- **Never** let a test suite regress; after every wave, `pytest tests/ -q` must pass.
- **Never** persist without an audit log entry (Phase 2g covers this).
- **Always** record `run_id`, `input_snapshot_id`, `rule_set_version`, and `config_fingerprint` on every run so replay works.

### 34.2 Exit criteria

The code agent may declare the build complete when:

- `pytest tests/ -q` returns `234 passed, 1 deselected` on a fresh clone.
- `pytest tests/perf -m perf -q` returns `1 passed`.
- Every requirement in `.kiro/specs/spark-rule-engine/requirements.md` maps
  to at least one test.
- Every correctness property P1-P38 (plus extension properties) has a
  property-based test with at least 100 Hypothesis examples.
- `BUILD_STATUS.md` is updated with final counts.
- `README.md` points newcomers to the correct documentation for their role.
