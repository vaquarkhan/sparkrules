# Feature gap inventory (spec vs repository)

This document enumerates features described in project specifications (for example `.kiro/specs/spark-rule-engine/`, `AI_REPRODUCTION_BLUEPRINT.md`, `USE_CASES.md`, `ARCHITECTURE.md`) that are not present in the `vaquarkhan/sparkrules` repository as of the stated inspection date. Use it to track remaining work; **implemented** items in the repo (Phases 1, 2b, 2m UDF registry, 2n output formats, 3 Workbench UI, 4 governance) are not repeated here.

| Field | Value |
|--------|--------|
| Inspection date | 2026-04-27 |
| Repo test baseline (stated) | 407 passed, 2 skipped, 1 deselected (perf) |
| Repo coverage gate | 100% line coverage on `src/sre` (`fail_under=100` in `pyproject.toml`) |

**Convention:** each gap section lists what is missing and concrete deliverables to close it so a code agent can execute item by item.

---

## 1. Phase 2a — Data quality (partial; most still missing)

**Present in repo:** basic DQ MVP (`src/sre/dq/engine.py` with not-null / between / in-set; WARN / ERROR severity; ROW / FIELD scope; `/dq/evaluate` endpoint; `dq_violations` Iceberg table).

**Missing**

- Severity levels — CRITICAL and INFO (repo only has WARN / ERROR)
- Tolerance attribute — e.g. `≤0.1%` nulls OK before firing (spec P40)
- Scope level — RELATIONSHIP (cross-table); repo has only ROW and FIELD
- Data contract format — `data_contract.yaml` with per-check severity, scope, tolerance, owner, schedule
- Quarantine routing — facts firing CRITICAL rules diverted to a `dq_quarantine` Iceberg table before downstream consumption
- Additional DQ primitives (sugar over DRL):
  - `ExpectColumnValuesToBeUnique(col)` — COUNT DISTINCT == COUNT
  - `ExpectColumnValuesToMatchRegex(col, pattern)`
  - `ExpectColumnSumToBeBetween(col, low, high)` — Pass_2 aggregate
  - `ExpectRowCountToBeWithin(low, high)` — dataset-level aggregate
  - `ExpectTableCountsToMatch(a, b)` — cross-dataset reconciliation
  - `FreshnessCheck(ts_col, max_age)` — temporal
- DQ properties (spec P39–P43):
  - P39 severity monotonicity (no silent severity downgrade without version bump)
  - P40 tolerance correctness
  - P41 quarantine completeness
  - P42 contract closure (running a contract ≡ union of declared rules)
  - P43 reconciliation commutativity
- Grafana DQ dashboard template
- DQ report artifact (PDF/HTML) for regulatory submission

---

## 2. Phase 2c — AI-assisted rule authoring (not implemented)

Only an `ai_provider: str | None` placeholder in config.

**2.1 Provider abstraction** — `AiProvider` protocol with adapters for: AWS Bedrock (Claude / Llama), OpenAI, Azure OpenAI, Google Vertex AI, Databricks Foundation Models, local Ollama (air-gapped).

**2.2 REST surface**

- `POST /ai/suggest-rules` — propose new rules from observed fact patterns
- `POST /ai/mine-dq-rules` — propose DQ checks from observed distributions
- `POST /ai/analyze-drift` — detect fire-rate drift and suggest adjustments
- `POST /ai/explain-rule` — natural-language explanation of a rule
- `GET /ai/suggestions` — pending-review queue
- `POST /ai/suggestions/{id}/approve` and `…/reject`

**2.3 Suggestion lifecycle** — every AI output stored with `is_active=false` and `source: AI_SUGGESTION` until human approves; linked `simulator_result` before promote (P46); audit log (model id, version, principal, prompt hash, response hash).

**2.4 Safety and compliance** — PII redaction, Bedrock Guardrails, Bedrock Knowledge Bases, rate limits (max N suggestions per tenant per day).

**2.5 Advanced AI** — drift (CUSUM / Bayesian change-point on fire rates), natural-language authoring with simulator validation and human approval.

**2.6 Properties** — P45 AI safety boundary, P46 simulator evidence, P47 PII redaction.

---

## 3. Phase 2d — Graph-enriched fraud (not implemented)

Zero matches on neptune / neo4j / tigergraph / graphframes / cluster_risk / n_hop_fraud.

- **3.1** `GraphSource` protocol (Neptune, Neo4j, TigerGraph, JanusGraph, Spark GraphFrames, in-memory/NetworkX for tests).
- **3.2** `GraphEnricher` — pre-eval decoration; precomputed vs live query; TTL cache; PII pseudonymous node IDs without `pii_reveal` role.
- **3.3** Graph-derived rule sugar — `GraphRiskAbove`, `NHopToKnownFraud`, `SharedAttributeVelocity`, `CommunityMembershipFlag`, `CentralityAnomaly`.
- **3.4** Graph replay — `GraphSource.snapshot_id()` in `config_fingerprint`; replay uses same snapshot.
- **3.5** Properties P48–P51 (snapshot determinism, idempotency, primitive expansion, PII redaction).

---

## 4. Phase 2e — ML model scoring as rule action (not implemented)

Zero matches on `invoke_model` / `ModelProvider` / `model_serving` / `model_id`.

- **4.1** `ModelProvider` — SageMaker, Bedrock, MLflow, Triton, Databricks, local ONNX.
- **4.2** DRL `invoke_model(model_id, fact)` in `then`; feature assembly; `action_output` with model id, version, features, score.
- **4.3** Replay — `(model_id, model_version)` pinned in `run_history`.
- **4.4** Properties P52–P54 (version pinning, score determinism, full explanation on invoke).

---

## 5. Phase 2f — Lineage and governance emission (not implemented)

Zero matches on openlineage / datahub / atlas / unity_catalog.

- **5.1** Events — OpenLineage START (inputs, rule set version, config fingerprint, profile); COMPLETE (outputs, metrics); FAIL (exception class + message).
- **5.2** Sinks — Marquez, DataHub, Unity Catalog, Atlas/Glue.
- **5.3** Rule-level linkage in `rule_results` (input table/snapshot, rule versions, author, AI id, graph snapshot, model id/version).
- **5.4** Properties P55–P56 (lineage completeness, audit chain).

---

## 6. Phase 2g — Full RBAC + SSO + multi-tenancy (mostly missing)

Repo: single API-key middleware; `namespace` on rules.

- **6.1 Authentication** — OIDC (Okta, Auth0, Azure AD, Google, Keycloak), SAML 2.0, mTLS, IRSA, instance profile.
- **6.2 Role-based access control (8 roles)**

| Role | Permissions |
|------|-------------|
| `rule_reader` | `GET` `/rules`, `/runs`, decision tables |
| `rule_author` | reader + `POST`/`PUT` rules, import, simulate |
| `rule_admin` | author + `DELETE`, activate, A/B test create |
| `run_operator` | `POST` `/runs`, replay, run metrics |
| `dq_steward` | data contracts, violations |
| `ai_reviewer` | approve/reject AI suggestions |
| `pii_reveal` | unmask redacted `bound_fields` |
| `platform_admin` | full + Catalyst + quota overrides |

- **6.3** Tenant isolation at catalog (Iceberg namespace per tenant; `tenant_id` from claims; per-tenant Spark session; metrics labels; 403 on cross-tenant table refs).
- **6.4** Append-only `audit_log` Iceberg table; RLD disabled; row per mutating call.
- **6.5** Properties P57–P59.

---

## 7. Phase 2h — Developer UX (partial)

**Present:** CLI (`tools/smoke_drl.py`), Python SDK, Workbench, Docker.

**Missing**

- **7.1** VS Code DRL extension; LSP (autocomplete, go-to-def, UDF); snippets.
- **7.2** Per-rule YAML scenario tests; `sparkrules rules test <handle>`; chaos/failure tests for P23/P27.
- **7.3** Java/Kotlin, Go, TypeScript (OpenAPI) clients.
- **7.4** CLI depth — `rules diff` wrapper, `ai suggest`, `dq contract apply`, `graph features`, `profile`, `runs list`, etc.

---

## 8. Phase 2j — dbt integration (not implemented)

`DbtFactSource`, `manifest_hash`, dbt package `sparkrules_dbt`, post-hook runs, OpenLineage to dbt nodes. **P60** dbt manifest pinning for replay.

---

## 9. Phase 2k — Fail-fast execution policy (not implemented)

`stop_on_fire`, `first_failure`, `fail_fast`, `stop_on_decline`, `execution_policy`.

- **9.1** Per-rule `stop_on_fire` — when rule fires, skip remaining rules for the fact.
- **9.2** Per–agenda-group mode (`first_failure`, `all_matches`, `first_match`).
- **9.3** Per-pipeline e.g. `stop_on_decline: true`.
- **9.4** Properties P61–P63.

---

## 10. Phase 2i — Strategic add-ons (none implemented)

NL authoring (2c), coverage analysis, deprecation workflow, shadow/canary, time-travel debugger, counter-factual, DT from examples, multi-region CRDT, marketplace, SOC2/PCI presets.

---

## 11. Phase 3 — Web UI depth (partial)

Workbench exists; **missing** proper diff UI, graph/agenda visualisation, AI review (2c), DQ dashboard, run replay, Monaco/AG Grid editors, A/B UI, time-travel UI (depends on 10.5).

---

## 12. Phase 4 — Scala production port (not implemented; repo “Phase 4” is governance)

sbt multi-module, ANTLR `Drl.g4`, ScalaCheck parity, real Spark strategies, Iceberg, Spark Connect gRPC, optional Spring Boot REST.

---

## 13. SQL_JOIN execution strategy (stub)

Runtime stub — `SqlJoinNotImplemented` (or equivalent); P17 may skip strategy equivalence for SQL_JOIN.

---

## 14. Billion-row scale depth (partial)

Harness at smoke scale; missing billion-row targets, cluster profiles, `perf_history` regression gate, skew handling as specified.

---

## 15. Engine-core features (not yet formalised in repo)

Backward chaining, beta network, explode-then-filter, schema migration tooling, per-rule Catalyst toggles, etc.

---

## 16. Observability depth (partial)

Prometheus, structlog, health present. **Missing** OpenTelemetry, trace propagation, per-rule cost, fire-rate metrics for drift, SLO/alerting rules as listed.

---

## 17. Security depth beyond API key

Vault/secret manager, key rotation, rate limits, request signing, CSP for Workbench, CORS, encryption at rest, rule signing, SLSA/in-toto.

---

## 18. Regulatory and compliance artifacts

SOC 2 / PCI / GDPR / 21 CFR Part 11 / HIPAA BAA / FedRAMP profile mappings — not ready-to-ship.

---

## 19. Operational documentation (missing)

Threat model, DR runbook, capacity planning, Drools/Blaze/ODM migration guides, formal API versioning policy.

---

## 20. Property-based test extensions (P39+)

P39–P43, P44, P45–P47, P48–P51, P52–P54, P55–P56, P57–P59, P60, P61–P63, P67, P68–P70 — Hypothesis with ≥100 examples each where applicable.

---

## Suggested implementation order (for agents / sequencing)

1. Phase 2k — fail-fast (smallest, high day-one value for auth / clinical / redemption)
2. Phase 2g — RBAC + OIDC
3. Phase 2a — DQ depth
4. Phase 2f — lineage
5. Phase 2c — AI assist
6. Phase 2d — graph fraud
7. Phase 2e — ML scoring
8. Phase 2j — dbt
9. Phase 2i — strategic add-ons (shadow, deprecation, coverage first)
10. Phase 4 — Scala port (parallel; few upstream deps)

This order is a recommendation; adjust for product and compliance priorities.
