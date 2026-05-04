# Production reference bundle

Operator-owned assets and runbooks that sit **next to** the core library. They are not imported by `sparkrules` at runtime; copy or adapt them into your platform repo.

| Path | Purpose |
|------|---------|
| [docs/DEPLOY_PRODUCTION.md](docs/DEPLOY_PRODUCTION.md) | Databricks / Glue / EMR sizing, networking, checkpoints |
| [docs/GOVERNANCE_WORKFLOW.md](docs/GOVERNANCE_WORKFLOW.md) | Dev → stage → prod, rollback, deprecation |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | STRIDE for API + Spark driver executors |
| [docs/SECURITY_SBOM.md](docs/SECURITY_SBOM.md) | SBOM (CycloneDX / SPDX), provenance, audits |
| [docs/SEC_HARDENING.md](docs/SEC_HARDENING.md) | Controls beyond `/metrics` + `SPARKRULES_MAX_RULEPACK_BYTES` |
| [grafana/grafana-sparkrules.json](grafana/grafana-sparkrules.json) | Starter dashboard (Prometheus text exposition) |
| [k8s/canary.yaml](k8s/canary.yaml) | Shadow + parity gate pattern (Argo Rollouts–shaped) |
| [benchmarks/BENCHMARK_CLUSTER.md](benchmarks/BENCHMARK_CLUSTER.md) | Large-cluster benchmark protocol and reporting |

Related runnable code:

- [../streaming/kafka_iceberg_structured_streaming.py](../streaming/kafka_iceberg_structured_streaming.py) — Kafka → micro-batch → `apply_drl` → Iceberg
- [../native/README.md](../native/README.md) — Native acceleration contract + PyO3 template
- [../vscode-sparkrules/](../vscode-sparkrules/) — VS Code extension calling `lsp-check`
- [../databricks/07_production_governance_deploy.ipynb](../databricks/07_production_governance_deploy.ipynb) — Databricks notebook
