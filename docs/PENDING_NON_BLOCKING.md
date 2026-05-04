# Non-blocking backlog (status)

These items are **not required** to adopt or run SparkRules in production. They describe optional hardening, longer research, or operator-owned wiring. For core scope and extension points, see [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md); for planned features, see [ROADMAP.md](ROADMAP.md).

Starter **runbooks and configs** live under [`examples/production/`](../examples/production/README.md) (deploy notes, STRIDE, Grafana JSON, canary manifest, cluster benchmark protocol). Treat them as templates until tailored to your platform.

---

| Category | Item | Why it's not blocking |
|----------|------|------------------------|
| Code | **Native Cython/Rust hot loop — not shipped** | **There is no production native hot loop in this repo.** The `sparkrules_native` namespace is reserved; shipped wheels use the **pure Python / V2** path. What exists today is a **bridge template** (`examples/native/bridge.py`) and a **PyO3 starter crate** (`examples/native/pyo3_template/`) for a **separate** implementation effort (multi-week). Req 27–29 in [REQUIREMENTS_V2_ENGINE.md](REQUIREMENTS_V2_ENGINE.md) describe the target; see [`examples/native/README.md`](../examples/native/README.md). |
| Code | **Full Kafka → Spark → Iceberg runnable job** | The CLI ships a **plan builder** only (`sparkrules.tools.stream_kafka_iceberg`). A production job needs your brokers, catalog, and SLOs. Reference: [`examples/streaming/`](../examples/streaming/README.md). |
| Code | **BUG-39: governance `platform_admin` cross-namespace** | **Resolved in API:** `POST /governance/sync-dev` resolves the active rule and uses its namespace for pins and audit when the caller has `platform_admin`. No need to change `X-Tenant-Id` per namespace for that endpoint. Other routes may still enforce tenant headers; validate per path. |
| Ops | **Grafana dashboard** | `/metrics` is available; dashboard import is a **config task**. Starter JSON: [`examples/production/grafana/grafana-sparkrules.json`](../examples/production/grafana/grafana-sparkrules.json). |
| Ops | **Kubernetes canary (shadow + parity)** | `shadow_parity_summary()` and related APIs exist; wiring **Rollouts** / mesh routing is a **config task**. Example manifest: [`examples/production/k8s/canary.yaml`](../examples/production/k8s/canary.yaml). |
| Docs | **Per-platform deploy runbook** | Operator-specific (Databricks DPUs, Glue, networking). Template: [`examples/production/docs/DEPLOY_PRODUCTION.md`](../examples/production/docs/DEPLOY_PRODUCTION.md). |
| Docs | **STRIDE threat model** | Buyer-specific trust boundaries. Template: [`examples/production/docs/THREAT_MODEL.md`](../examples/production/docs/THREAT_MODEL.md). |
| Validation | **Real 200-node cluster benchmark** | Budget and access to large clusters; methodology: [`examples/production/benchmarks/BENCHMARK_CLUSTER.md`](../examples/production/benchmarks/BENCHMARK_CLUSTER.md). |
| Ecosystem | **Pen test, customer case study, conference talk, vendor partnerships** | Non-code or relationship/time-bound; does not block library releases. |

---

## Related

- [SECURITY_SBOM.md](../examples/production/docs/SECURITY_SBOM.md) — SBOM and supply-chain practices  
- [SEC_HARDENING.md](../examples/production/docs/SEC_HARDENING.md) — Beyond metrics and rule-pack size caps  
- [GOVERNANCE_WORKFLOW.md](../examples/production/docs/GOVERNANCE_WORKFLOW.md) — Promotion and rollback narrative  
