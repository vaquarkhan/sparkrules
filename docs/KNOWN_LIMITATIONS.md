# Known limitations and blueprint gaps

This document records **intentional honesty** about what is **not** production-complete compared to a full “Phase 2g + UI tier” enterprise blueprint. It complements [FEATURES.md](FEATURES.md) (what exists) and [ROADMAP.md](ROADMAP.md) (planning).

---

## Identity and access (Phase 2g)

**OIDC / SAML / full federation**  
- The service supports **`SPARKRULES_API_KEY`**, `X-Principal` / `X-Tenant-Id` / `X-Roles` headers, and an **`SPARKRULES_AUTH_MODE`** switch (`local`, `oidc`, `mtls`, `iam`) in [security.py](https://github.com/vaquarkhan/sparkrules/blob/main/src/sre/api/security.py).  
- **OIDC mode** enforces optional issuer/audience checks on environment variables; the JWT payload is still parsed **without** full signature verification in the current helper path (suitable for dev/tests behind a trust boundary, not a complete IdP integration).  
- **SAML** is **not** implemented.  
- **mTLS** mode checks for a **header** `X-Client-Cert-Subject` (simulating a gateway-passed identity), not a real TLS client-cert stack inside this process by default.  
- **Reason:** real federated identity needs deployment-specific gateways, key stores, and verified JWTs—this repo provides hooks and local/dev behavior, not a turnkey IdP product.

**Per-tenant Iceberg namespace isolation**  
- **Namespace** is a field on the **Rule** and used for governance, filtering, and tenant-scoped access checks.  
- There is **no** enforcement of separate **Iceberg catalog / namespace** per tenant at the catalog layer; the in-process “Iceberg-like” table and metadata paths are for **modeling and tests**, not multi-tenant lake isolation.  
- **Reason:** true isolation requires a hosted catalog, IAM, and per-tenant table paths in your data plane.

**Full RBAC “blueprint” enumeration**  
- Authorization uses **string role names** in `require_any_role` (e.g. `rule_reader`, `rule_author`, `rule_admin`, `run_operator`, `dq_steward`, `ai_reviewer`, `pii_reveal`, plus **`platform_admin`** as superuser in [security.py](https://github.com/vaquarkhan/sparkrules/blob/main/src/sre/api/security.py)).  
- There is **no** public **`GET /roles`** or OpenAPI **enum** that lists “the eight roles” for operators; role sets are **distributed across route definitions** in `app.py`.  
- **Reason:** the blueprint’s named role set should be **confirmed in your integration tests** and documentation runbooks, not assumed from a single central registry in this repo.

---

## Spark and distributed execution

**SQL_JOIN, batch, and streaming**  
- Multi-pattern and “join-style” behavior can be exercised in **local / pure-Python** execution (including list-binding expansion in the **local** executor path).  
- **PySpark** is often installed (e.g. as a test dependency), but a **`SparkSession` is not created** on the default **HTTP simulation / workbench** evaluation path—so **distributed** scale is **not** demonstrated there.  
- **Reason:** wiring rules to a cluster DataFrame, broadcast packages, and executors is **deployment-specific**; the repo provides hooks and abstractions, not a hosted cluster.

### Evidence: what a live run actually shows

In the default API path (e.g. **`POST /simulations`**, Workbench **Simulate**, or in-process **`RuleExecutor.run()`** without a Spark integration):

| Observation | Meaning |
|-------------|---------|
| `SparkSession.getActiveSession()` is **`None`** | **No** `SparkSession` was created by this evaluation. |
| Single **uvicorn** (or similar) process | **Pure-Python**, **single-process** mode: no Spark executors, no distributed workers. |
| **PySpark** present in the environment | A **library on the classpath**, not proof of use. The engine does not, on that path, create a session or ship work to the cluster. |
| Throughput in the **~single-digit–10k evaluations/sec** range on one machine | Consistent with **interpreted** predicate / AST-style evaluation in CPython—not **Catalyst**-compiled Spark SQL. |

Example back-of-thevelope: if effective throughput were on the order of **~10² facts/sec per core** in pure Python, reaching **10⁹** rows without parallelizing the **rule engine** across executors implies **unrealistic** wall-clock on a single core; **distributed** Spark (or another scale-out path) is required for billion-row **wall-clock** claims.

### Product claims vs measured reality

| Claim | Reality |
|-------|---------|
| **Drools-style rule engine** | **True** — predicates, `when`/`then`, salience, activation groups, version store behave as designed. |
| **“Apache Spark … for … billions of transactions”** (marketing-style) | **Not demonstrated** on the default path. **PySpark** may be installed; **no** `SparkSession` is used for default evaluation. Optional tests under `tests/spark/` need a JVM and only cover **partition iterator** wiring—not a full **cluster** proof. |
| **“Scales to billions of rows in seconds”** | **Not shown** in-repo. Throughput on the pure-Python path is **process-local**; seconds-at-billion-row scale requires **partitioned** execution on a real cluster (and measured evidence). |
| **Rule evaluation over Iceberg snapshots** | **Partial** — the **Iceberg-like** in-memory snapshot model and APIs work for tests and modeling; **live** Iceberg catalog integration is **environment-specific** and not proven by the default single-process benchmark. |

**Honest summary:** The **rule semantics** and **store** behavior are **legitimate** for a Python-first Drools-style engine. The **“Spark”** in the product name is **aspirational** until you **wire** evaluation to **`mapPartitions`** (or equivalent) over a **DataFrame**, **broadcast** the `CompiledRulePackage` (see `sre/transport/broadcaster.py`), and run on a **real** Spark cluster. Primitives exist (`sre/spark/dataframe.py`, broadcaster, Iceberg-like store); **nothing** in the default **`/simulations`** or unwrapped **`RuleExecutor.run()`** path **invokes** them automatically.

---

## Workbench and API (UI tiers)

**Tier 1.1 — bulk simulation upload (CSV / JSONL / XLSX)**  
- There is **no** `POST /simulations/bulk` (or similar) in the public API. Simulations are **POST `/simulations`** (and related variants) with a **JSON body**.  
- The Workbench **Simulate** view expects **hand-typed** fact JSON (and DRL in Monaco), not a file upload.  
- **Reason:** bulk upload would need streaming parsers, size limits, and error reporting—**not** implemented in the static shell.

**Tier 2.3 — graph-based rule / agenda visualisation (e.g. React Flow)**  
- There is **no** React Flow (or similar) **visual graph** in [workbench](https://github.com/vaquarkhan/sparkrules/tree/main/src/sre/api/static/workbench).  
- A **`POST /graph/enrich`** API exists for **enrichment** payloads, not a full interactive agenda designer.  
- **Reason:** visual rule graphs are a **separate UI product**; not in scope of the current static Workbench.

**Tier 3.1 — full run history UI**  
- There is **no** `GET /runs` (or equivalent) for listing **arbitrary** execution history for the Workbench. Internal tables (e.g. `run_history`, `debug_runs`, audit) back **specific** features, not a general-purpose “runs browser”.  
- **Reason:** a full run catalog needs retention policy, query indexes, and UI design—**not** shipped as a first-class run explorer.

---

## How to use this document

- **Product / sales:** Do not claim SAML, catalog-level multi-tenant Iceberg isolation, or distributed Spark on the default API path without qualification.  
- **Engineering:** Use this as a **checklist** for proposals (identity gateway, cluster integration, Workbench 2.0).  
- **Tests:** The requirement ladder and property tests **do** cover in-repo requirements; this file tracks **gaps vs. an external blueprint**, not a failure of existing tests.
