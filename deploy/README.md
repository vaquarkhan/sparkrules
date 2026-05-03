# Deployment overview

SparkRules ships as a Python package and HTTP API. Runtime target (Glue, Databricks, Dataproc, Synapse) is selected via configuration; see `sparkrules.runtime.EngineConfig` and `runtime_conf()`.

This directory contains **reference** scripts and notes. You must supply cloud credentials, IAM roles, and network settings in your own account.

| Target | Guide |
|--------|--------|
| AWS Glue | [aws-glue/README.md](aws-glue/README.md) |
| Databricks | [databricks/README.md](databricks/README.md) |
| GCP Dataproc | [gcp-dataproc/README.md](gcp-dataproc/README.md) |
| Azure Synapse | [azure-synapse/README.md](azure-synapse/README.md) |

For a local or container run, use `docker compose up --build` from the repository root and open `http://127.0.0.1:8000/workbench/`.
