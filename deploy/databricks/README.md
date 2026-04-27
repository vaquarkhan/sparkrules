# Databricks

1. Create a cluster or SQL warehouse with **Spark 3.x**.
2. Install this package: `%pip install /Workspace/path/to/sparkrules` (wheel) or add as a library from Artifactory.
3. Set `EngineConfig(platform="databricks", spark_version="3.5", ...)` and merge `runtime_conf()` into your Spark session `conf`.
4. For interactive rule editing, use the in-repo **Workbench** (`/workbench/`) on a long-lived API host; Databricks notebooks can call the same HTTP API if you deploy the service alongside.

Secrets and workspace URLs are account-specific; keep them in Databricks **secrets** or your CI variables.
