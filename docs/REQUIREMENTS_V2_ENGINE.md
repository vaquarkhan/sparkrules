# Requirements: V2 Optimized Rule Engine

This document is the **normative** requirements set for the V2 execution architecture (compilation, classification, Spark/Python paths, and optional native acceleration). Internal planning drafts may exist locally but **this file is authoritative** for what the OSS package targets.

---

## Document control

| Field | Value |
|-------|-------|
| **Audience** | Engineering, QA, PM, security reviewers |
| **Scope** | `sparkrules` compiler, executors (`LocalRuleExecutor`, `SparkRuleExecutor`, `pandas` path), `apply_drl` / `iter_rule_rows`, `RulePack` lifecycle |
| **Out of chain** | Workbench UX, REST API unrelated to evaluation, unrelated stores — unless they surface V2 rollout flags |

Requirements are numbered **Req 1–29** (original engine scope), plus **Req 30–37** (cross-cutting: rollout, observability, resources, security, versioning, deprecation, native program).

---

## 1. Phased specification (delivery model)

To avoid a single high-risk gate, delivery is partitioned into **three specification tracks**. Tracks may ship in sequence; **cross-cutting Req 30–37 apply to every track** once V2 touches production workloads.

### Spec A — Core executor rebuild (minimum viable V2)

**Includes Req 1–18** plus **Req 19–24** (these complete the runnable Spark/Python product; they are bundled with Spec A for release planning even though numbering places some after 18).

| Req | Title |
|-----|-------|
| 1 | AST-to-SQL Translator |
| 2 | Closure Compiler |
| 3 | Alpha Network Completion |
| 4 | Rule Classifier Wiring |
| 5 | RulePack Data Structure |
| 6 | Strategy A: SQL_PUSHDOWN |
| 7 | Strategy B: ALPHA_SHARED |
| 8 | Strategy C: PYTHON_FALLBACK |
| 9 | LocalRuleExecutor |
| 10 | Typed Output Schema |
| 11 | Backward-Compatible `apply_drl` |
| 12 | Cross-Path Equivalence Testing |
| 13 | Action Value SQL Translation |
| 14 | Nested Struct Column Access |
| 15 | Schema Validation |
| 16 | Alpha Column Cleanup |
| 17 | Cross-Strategy Salience |
| 18 | Performance Targets |
| 19 | `iter_rule_rows` Optimization |
| 20 | Pickle-Safe Broadcast |
| 21 | Regex Compatibility |
| 22 | Pandas Batch Evaluation |
| 23 | Hot-Swap Rule Reloading |
| 24 | Agenda / Activation Group Semantics |

**Exit criterion:** Production workloads can run on Spec A alone with Req 30–37 satisfied for rollout and observability.

### Spec B — Rete-style Python optimizations

**Req 25–26** — reduces single-node Python latency via structural sharing (`FactView`, range-merged alphas).

**Dependency:** Spec A.

### Spec C — Native extension (optional accelerator)

**Req 27–29** plus **Req 37** — C/Rust hot path, wheels, CI, ownership. Highest build and supply-chain risk.

**Dependency:** Spec A (and realistically B if Python path must stay within SLA without native).

**Program expectation:** Typical calendar **8–14 weeks** of dedicated systems work for initial cross-platform wheels; ongoing maintenance per Req 37.

---

## 2. Non-goals (explicit scope exclusion)

The following are **not** required deliverables for V2. PM and field teams must **not** treat their absence as a defect against this spec.

1. **Complex Event Processing (CEP)** — sliding/event windows, temporal operators, aggregate-over-stream semantics.
2. **Truth maintenance / TMS** — automatic retraction based on logical dependencies beyond current rule semantics.
3. **Visual DMN or DRL designer** — modeling GUIs (DMN/XML round-trip tooling may exist elsewhere; pixel-perfect Drools authoring parity is excluded).
4. **Multi-tenancy redesign** — per-tenant isolation, new RBAC model, or row-level security in the engine kernel (consumers integrate via orchestration layers).
5. **Streaming-first CEP patterns** — Flink-style pattern matching beyond batch / micro-batch Spark.
6. **Managed SaaS rollout** — hosting, quotas, billing, org provisioning (product packaging is out of scope).
7. **Guaranteed bitwise-identical pickles** across Python minor versions — serialization follows Req 34 compatibility policy instead.

---

## 3. Requirement details (Req 1–29)

### Req 1 — AST-to-SQL Translator

Translate single-fact DRL predicates (supported subset) to Spark SQL expressions suitable for `F.expr(...)`. Fail closed with **`TranslationError`** when unsupported.

### Req 2 — Closure Compiler

Compile supported predicates (and RHS where applicable) to **pickle-compatible** Python callables invoked on the PYTHON_FALLBACK and local paths.

### Req 3 — Alpha Network Completion

Share evaluation of atomic predicates across rules (**Rete-style alpha sharing**) on paths that consume the alpha layer; AND-chains flattened per design in `compiler/alpha_network.py`.

### Req 4 — Rule Classifier Wiring

Every rule classified into exactly one of **SQL_PUSHDOWN**, **ALPHA_SHARED**, **PYTHON_FALLBACK** per deterministic rules documented in code (including Req 21 regex override).

### Req 5 — RulePack Data Structure

- Holds classified rules grouped by strategy; **salience ordering** applied for execution planning.
- **Serializable** via `serialize()` / `deserialize()` per Req 34.
- **`drl_hash`** remains the SHA-256 of canonical DRL bytes for diagnostics.

### Req 6 — Strategy A (SQL_PUSHDOWN)

Predicate + eligible actions evaluated via Catalyst **`F.expr`** (or equivalent) without per-row Python UDF for predicate evaluation.

### Req 7 — Strategy B (ALPHA_SHARED)

Shared boolean / scalar alpha columns merged with deterministic AND-reduction consistent with Req 17 tie-breaking.

### Req 8 — Strategy C (PYTHON_FALLBACK)

Compiled closures (+ alpha where applicable) in **`mapPartitions`** or row-wise equivalents; pickle-safe payloads per Req 20.

### Req 9 — LocalRuleExecutor

Scores/applies batches in-process with **`score`**, **`apply`**, **`refresh_rules`** symmetry with Spark executor semantics modulo platform limits.

### Req 10 — Typed Output Schema

Outputs expose **`r_<rule>`**, typed **`action_<field>`**, **`fired_any`** (names adapted to dialect: Spark vs pandas) consistently across strategies.

### Req 11 — Backward-Compatible `apply_drl` / `iter_rule_rows`

- **`use_v2` flag** retained through deprecation per Req 36.
- **Default policy:** Product default may be **`use_v2=True`** only after **Req 30** staged rollout milestones are met in each environment (`dev → stage → prod`).
- **`use_v2=False`** path preserved until deprecation milestone; parity tests mandated per Req 12 and Req 30.

### Req 12 — Cross-Path Equivalence Testing

Deterministic test corpus proving **matching outcomes** among reference evaluator, closure path, alpha path, Spark strategies (within supported subset). Any intentional divergence MUST be flagged with an explicit **`XFAIL` rationale** logged in repo.

### Req 13 — Action Value SQL Translation

Literal/simple assignments translatable for SQL strategy; fall back consistently per Req 4.

### Req 14 — Nested Struct Column Access

Field paths into structs supported as documented; schema validation surfaces **`SchemaValidationError`** on mismatch.

### Req 15 — Schema Validation

Input DataFrame schemas validated before expensive planning; actionable errors (**no silent coercion** unless explicitly documented).

### Req 16 — Alpha Column Cleanup

Temporary **`_a_*`** (or equivalent) columns removed before returning user-visible DataFrames.

### Req 17 — Cross-Strategy Salience

Merged action outputs MUST respect **effective priority**:

1. **Primary sort:** descending integer **salience**.
2. **Secondary sort:** ascending **rule name** in Unicode code-point order (Python `sorted` over `str`, after NFC normalization upstream if authoring allows mixed-compat names).
3. **Tertiary sort:** ascending **compilation index** — position of the rule in the ordered list **`RulePack.rules` after `from_drl` classification** (not regrouped per strategy bucket alone).

Implementations MUST use this tuple for **COALESCE ordering**, **pandas merge**, and **local executor** RHS winner selection where multiple rules touch the same `result` field across strategies.

**Rationale:** Salience ties are otherwise **non-deterministic** across Spark partitioning and pandas row order.

### Req 18 — Performance Targets

- **Smoke (single machine / `local[*]` bounded):** As documented for representative rule packs (CI micro-benchmark tier).
- **Cluster-scale evidence:** Extended by Req 35 — single-node Req 18 alone is insufficient for declaring production readiness on large clusters.

### Req 19 — `iter_rule_rows` Optimization

Compiled closures and alpha-aware evaluation preferred over raw AST interpretation when `use_v2=True`.

### Req 20 — Pickle-Safe Broadcast

Broadcast **serialized RulePack bytes** (`protocol=4` minimum per current API); partitions rebuild closures deterministically.

- **Req 20.4 (Broadcast payload sizing):**
  - **Observation:** Typical text DRL packs **&lt; 100 KB serialized** per ~1000 simple rules holds in benchmarks.
  - **Requirement:** Implementations SHOULD emit **warnings or metrics** when `len(serialize())` exceeds **`max_broadcast_bytes`** (configurable default **4 MiB**); Req 32 defines strict caps where products require hard limits.

### Req 21 — Regex Compatibility

Python-only regex constructs force **PYTHON_FALLBACK**; Spark-aligned patterns retain SQL classification when predicates otherwise qualify.

### Req 22 — Pandas Batch Evaluation

`apply_pandas` (or successor) evaluates consistent semantics with **`pandas.eval`** when strategy allows vectorization; deterministic fallback mirrors Spark Strategy C semantics.

### Req 23 — Hot-Swap Rule Reloading

`refresh_rules(drl)` (and Spark equivalent) swaps rules without restarting processes; versioning hooks per Req 34.

### Req 24 — Agenda / Activation Group Semantics

- **Agenda groups:** deterministic stage ordering per documented semantics aligned with Drools-lite subset (same as current product behavior in tests).
- **Activation groups:** **XOR semantics** among rules in same group — only one firing **win** must be deterministic:
  **(-salience, rule_name NFC asc, compilation index asc)** selects the survivor when multiple LHS match — identical tuple as Req 17.

### Req 25 — FactView with `__slots__`

Zero-copy-ish field reads on structured rows for beta network path (documentation in compiler/executor modules).

### Req 26 — Range-Merged Alpha Nodes

Structural sharing for range predicates as implemented in alpha layer; correctness covered by Req 12.

### Req 27 — Native Extension (Cython/Rust)

Optional wheel delivering accelerated hot-loop for kernels approved in design doc; MUST NOT be required for import of `sparkrules` core package.

### Req 28 — Native Extension Strategy C

Native path attaches to Strategy **C** (and only published interfaces agreed in threat model Req 33).

### Req 29 — Native Compilation Pipeline

**`maturin` / `cibuildwheel`** (or equivalent) producing audited wheels:

- **`manylinux`** + **macOS arm64** + **Windows amd64**.
- **Py** versions aligned with OSS matrix in CI.
- **Req 37** adds CI gate policy when native artifacts fail — **fallback to pure Python MUST remain green**.

---

## 4. Cross-cutting requirements (Req 30–37)

### Req 30 — Rollout, Migration, and Feature Flags

1. **Pickled RulePack migration:**
   On upgrade, **`deserialize(bytes)` MUST** check **format version / magic** per Req 34; reject with **`ValueError`** (or **`RulePackVersionError`**) documenting required rebuild path (**recompile from DRL** — canonical source-of-truth).
2. **Staged rollout:** `use_v2=True` promoted only after **`dev`** shadow compare then **`stage`** canary (**Req 31** dashboards) before **`prod`** default flip.
3. **Telemetry:**
   Emit counters/histogram tags: **`executor_version`** (`v1|v2`), **`strategyhistogram`**, **`classifier_fallback_count`**, **`paridadelta`** (paired diff rate if shadow mode).
4. **Shadow mode (optional tooling):** API or job config may run dual evaluation on sampled fractions for regression detection (**no customer-facing semantics change unless flag says promote**).

### Req 31 — Observability

1. **Metrics (pull or push adapters product-specific — wire points required in OSS):**
   - Per-strategy **`rows_evaluated`**, **`rules_fired`**, **`evaluation_latency_ms`** histograms.
   - **`classification_counts`** per rule or aggregated by strategy outcome.
   - **`translation_failures`** and **`spark_fallback`** rates.
2. **Structured logs:** INFO-level **`rule_id`, `strategy`, `salience`, `reason_codes`** on firing when log level permits; WARN on translation fallback.
3. **Debug hook:** **`RulePack.debug_classification()`** returns machine-readable breakdown (columns: rule name → strategy rationale code). Public API SHOULD be documented in HOW_IT_WORKS / SPARK_INTEGRATION after implementation.

### Req 32 — Resource Bounds

1. **Driver / executor JVM/CPU memory:** Publish **engineering guidelines** — e.g., **RulePack working set budget** `≤ 512 MiB` default soft cap before warning for **10 k-rule** textual packs (*calibrated empirically*); hard caps enforced only when user configures (**opt-in circuit breaker OOM avoidance** beyond CPython/OS responsibility).
2. **Broadcast caps:** **`max_broadcast_bytes`** default **64 MiB** (reject or split job when exceeded unless operator override); ties to Req 20.4.
3. **Closure proliferation:** Compiled closure count MUST scale **linearly with rule count**, not **`O(rules²)`**; document worst-case auxiliary structures.

### Req 33 — Security (DRL Treat as Code)

1. **Arbitrary execution:** Trusted DRL authoring only under established governance; OSS documents that **custom action expressions execute as Python**. Sandboxing (**RestrictedPython**, WASM, DSL subset) **out-of-scope unless added as future spec** — current requirement is disclosure + recommend **immutable rule promotion** (**GOVERNANCE.md** workflows).
2. **SQL injection / identifier injection:**
   **`F.expr` strings MUST** be assembled only from translator output with **validated identifiers** (**no raw string splice** from untrusted facts). Quote or reject rule names column aliases that violate **`^[a-zA-Z_][a-zA-Z0-9_]*$`** (or widen only after security review).
3. **Native boundary:** Req 37 — **validated buffer sizes**, **no deserialization of untrusted pickle** beyond RulePack whitelist path.

### Req 34 — RulePack Serialization Versioning

Serialized blob MUST:

1. Start with **explicit version header** `{magic, semver_major, semver_minor}` before pickle payload OR define **pickle-compatible dispatch** shim (implementation choice — document in module docstring).
2. Bump **minor** for additive-safe fields; **major** bump for breaking layout (requires rebuilt packs).
3. **Compatibility:** Support **deserialize N−1 minor** until deprecation notice (**two minor releases minimum** recommended).

*(Until header ships, pickled artifacts remain **deployment-local** — upgrade guide MUST say “re-export from authoritative DRL”.)*

### Req 35 — Cluster-Scale Performance Validation

Declare performance requirements **beyond Req 18 smoke:**

- Evidence plan: **`linear scaling`** through **≤ 200** equivalent Spark executors on **≥ 100 M row** deterministic fixture (hardware profile documented — e.g., `r5.2xlarge` driver + `r5.large` cores).
- **Acceptance metric:** Stage time scales **within 25% variance** of IDEAL linear projection after warmup (document methodology in **`docs/BENCHMARKS.md`** lineage).

*(CI may run reduced factor — full evidence typically release gate.)*

### Req 36 — `use_v2=False` Deprecation Policy

Maintain dual path maximum **four minor semver releases after `use_v2=True` GA default.** After:

- Freeze feature dev on **`use_v2=False`** (bugfix only **one minor** overlap).
- Remove path in **semver major**.

Test matrix SHOULD drop **`use_v2=False`** conformance classes after freeze except migration smoke.

### Req 37 — Native Extension Program (Operational)

1. **CI gate:** **`optional` workflow** MAY fail without blocking **`main`** merge; **`required`** workflow validates **fallback wheel absent** correctness on **pure Python**.
2. **Cost awareness:** Maintain **budget doc** (`docs/BENCHMARKS.md` appendix) estimating **minute × runner matrix** (`3 OS × Python matrix`).
3. **Ownership:** Named **platform owner** rotate (MAINTAINERS equivalent) accountable for toolchain drift (Rust toolchain months).
4. **SLA:** **critical native defect** ⇒ hotfix disables native optional extra or **pins previous wheel** (`<version`) documented in SECURITY / release notes (**≤ 72h** acknowledgment target OSS best-effort).
5. **Input validation:** All native FFI accepts **validated sizes** copied from bytecode **RulePack envelope** (`max_actions`, bounded strings).

---

## 5. Risk register

| Risk | Severity | Mitigation (requirement) |
|------|----------|---------------------------|
| Native extension breaks CI for extended periods | **High** | Req 37.1 (**optional job** vs core); Req  **29** fallback path |
| `use_v2=True` prod regression undetected | **High** | Req **30**, **31**, **36** |
| Identifier / SQL misuse via crafted rules | **Medium** | Req **33.2**, tests for unsafe alias rejection |
| 10 k-rule pack OOM driver | **Medium** | Req **32**, operational guidance |
| v1 vs v2 dual maintenance drag | **Medium** | Req **36** deprecation |
| Tie leaks nondeterministic winner | **Low** | Req **17**, **24** explicit ordering |
| Unversioned pickles break rollout | **Medium** | Req **34**, **30.1** |
| Horizontal scale unknown | **Medium** | Req **35** |

---

## 6. Consolidated requirement index & status summary

Legend: ✅ implemented in OSS code + tests | ⚙ hybrid (policy / external evidence still on you) | 🔶 Spec C pending | 📋 procedural-only

| Req | Title | Priority | Typical track |
|-----|-------|----------|---------------|
| 1 | AST-to-SQL Translator | High | Spec A ⚙ |
| 2 | Closure Compiler | High | Spec A ⚙ |
| 3 | Alpha Network | High | Spec A ⚙ |
| 4 | Classifier | High | Spec A ⚙ |
| 5 | RulePack | High | Spec A ⚙ |
| 6–8 | Strategies A–C | High | Spec A ⚙ |
| 9 | Local executor | High | Spec A ⚙ |
| 10 | Typed schema | Medium | Spec A ⚙ |
| 11 | apply_drl compat | High | Spec A ⚙ |
| 12 | Cross-path equiv | High | Spec A ✅ tests |
| 13–14 | Actions / structs | Medium | Spec A ⚙ |
| 15–16 | Schema / cleanup | Med–Low | Spec A ⚙ |
| 17 | Cross-strategy salience | Medium | Spec A ⚙ |
| 18 | Perf targets smoke | High | Spec A ⚙ |
| 19–22 | Iter rows / pickle / regex / pandas | Medium | Spec A ⚙ |
| 23 | Hot reload | Medium | Spec A ⚙ |
| 24 | Agenda / activation | Medium | Spec A ⚙ |
| 25–26 | FactView / merged alphas | Medium | Spec B ⚙ |
| 27–29 | Native extension suite | Low | Spec C 🔶 |
| **30** | Rollout / migration | **High** | **✅** `sparkrules.runtime.rollout` (+ env flags) |
| **31** | Observability | **High** | **✅** `sparkrules.runtime.engine_metrics` + `LocalRuleExecutor` INFO logs + `classification_rationale` |
| **32** | Resource bounds | **Medium** | **✅** optional hard cap ``SPARKRULES_MAX_RULEPACK_BYTES`` + soft serialize warn (10 k-rule memory = ops guidance §32) |
| **33** | Security disclosures + validation | **High** | **✅** Spark alias validation + spec trust text |
| **34** | Serialization versioning | **High** | **✅** `SRRP` envelope + ``RulePackVersionError`` |
| **35** | Cluster scaling evidence | **Medium** | **⚙** methodology in §35 + **BENCHMARKS.md** appendix (runtime evidence stays customer-owned) |
| **36** | use_v2 deprecation | **Medium** | **⚙** policy text + dual-path tests (**📋** full removal gated on semver roadmap) |
| **37** | Native program / CI SLA | **Low** | **🔶** Spec C + **⚙** cost appendix |

> **Footnote:** Core Req **30–34** ship with concrete OSS hooks. Req **35–37** mix **engineering policy** (**⚙**) with optional native work (**🔶**).

---

## 7. Sign-off checklist (engineering + PM)

- [x] Non-goals communicated to roadmap consumers (**§2**).
- [x] Phase A/B/C planning artifacts reference this doc.
- [x] Rollout (**Req 30**) + engine metrics (**Req 31**) implemented in `sparkrules.runtime.*` (wire into your release playbook).
- [ ] **Req 36** semver milestone recorded for removing `use_v2=False`.
- [x] Security reviewer acknowledged **§Req 33** trust boundaries (**SECURITY.md**).
- [x] Pickle versioning (**Req 34**) enforced for new `serialize()` payloads.
