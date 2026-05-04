# Databricks — Spark jobs with SparkRules (Terraform)

Use **Databricks Runtime** with **PySpark** and install **SparkRules** on the cluster via:

- **Init script** / **pip** in the cluster policy, or
- **Wheel** on **DBFS** / **Unity Catalog** volume + `%pip install /Volumes/...`

## Terraform

This bundle wires **variables** for workspace host, catalog, and job naming. The **Databricks provider** requires:

```bash
export DATABRICKS_HOST="https://<workspace>.cloud.databricks.com"
export DATABRICKS_TOKEN="dapl..."
```

Or use **account-level** OAuth with newer provider settings (see [Databricks Terraform](https://registry.terraform.io/providers/databricks/databricks/latest/docs)).

## Job pattern

1. Store DRL in `/Workspace/Rules/policy.drl` or UC volume.
2. Notebook or Python task: `from sparkrules.spark import apply_drl` after `SparkSession` is active.
3. For streaming, use **Structured Streaming** in a **long-running job cluster**; checkpoint to cloud storage.

## Files

| File | Purpose |
|------|---------|
| `versions.tf` | Terraform + `databricks/databricks` provider |
| `variables.tf` | Workspace naming, `create_resources` |
| `main.tf` | Optional `databricks_notebook` / `databricks_job` placeholders (disabled by default) |
| `outputs.tf` | Echo configuration hints |

Existing notebook: [../../databricks/07_production_governance_deploy.ipynb](../../databricks/07_production_governance_deploy.ipynb).
