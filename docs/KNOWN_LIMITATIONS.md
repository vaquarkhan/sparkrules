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
- **PySpark** is a dependency, but a **`SparkSession` is not created** on the default **HTTP simulation / workbench** evaluation path—so **distributed** scale is **not** demonstrated there. A live run can correctly show *no* active Spark session on that path.  
- **Reason:** wiring rules to a cluster DataFrame, broadcast packages, and executors is **deployment-specific**; the repo provides hooks and abstractions, not a hosted cluster.

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
