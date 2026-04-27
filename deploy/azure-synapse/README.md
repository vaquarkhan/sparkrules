# Azure Synapse Spark

1. Create a **Spark 3.x** pool in Azure Synapse Analytics.
2. Import the `sparkrules` package as a **workspace** or `pip` library on the pool.
3. Set `EngineConfig(platform="azure-synapse", ...)` and merge `runtime_conf()` into the Spark session.
4. Mount ADLS/ABFS paths for Iceberg or Delta; wire credentials through Synapse **linked services**.

Workspace and tenant settings are not checked in; configure through Azure Portal or Bicep in your org.
