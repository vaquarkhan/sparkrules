# AWS Glue

1. Package this project into a Wheel or copy the `src/sparkrules` tree into a Glue job script location.
2. Set job **Python version** to match the cluster (3.11+).
3. Set **Spark** to 3.x and align with `EngineConfig(spark_version="3.5", platform="glue", glue_dpu=...)`.
4. Pass configuration as environment variables or a small `job_params.json` that your job reads and applies via `runtime_conf(EngineConfig(...))`.
5. For API-style workloads, run the FastAPI app on ECS/Fargate or API Gateway + Lambda (with adapter); Glue is best for batch rule evaluation over large tables.

Example parameter file `glue_params.example.json` documents keys you can map to `EngineConfig`.
