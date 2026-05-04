# GCP — Dataproc / GKE + SparkRules (Terraform)

Typical deployments:

| Runtime | Where SparkRules runs |
|---------|------------------------|
| **Dataproc** | PySpark batch / session on YARN or Dataproc Serverless; `pip install sparkrules[spark]` via **initialization actions** |
| **GKE** | Spark Operator or Dataproc-on-GKE; custom image with SparkRules wheel |
| **Dataflow** | **Java/Beam** — not Python SparkRules native; use **HTTP** sidecar to SparkRules API for scoring |

## This Terraform

Creates a **GCS bucket** for wheels + DRL artifacts and a **service account** (optional) that Dataproc nodes can use with **Workload Identity** or **VM scope** to read rules.

## Environment

- `gs://.../rules/policy.drl` passed as job property or downloaded in driver `main`.
- Match **Python 3.11+** on workers to the SparkRules wheel you ship.

## References

- `deploy/gcp-dataproc/` in repo root (if present).
- Spark: `examples/spark/apply_drl_local.py` (swap cluster URL).
