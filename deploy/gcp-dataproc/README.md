# Google Cloud Dataproc

1. Create a **Dataproc** cluster (Spark 3.x image).
2. Submit a PySpark job that installs or imports `sparkrules` and sets `EngineConfig(platform="gcp-dataproc", ...)`.
3. Apply `runtime_conf()` keys to the Spark `SparkConf` before `SparkSession` creation where applicable.
4. For object storage, pass Iceberg/Delta/Hudi table paths as job arguments; validate inputs with `validate_fact_source()` in your job bootstrap.

Network, service accounts, and GCS paths are your responsibility; not automated here.
