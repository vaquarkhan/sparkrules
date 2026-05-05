# AWS Glue

1. Package this project into a Wheel or copy the `src/sparkrules` tree into a Glue job script location.
2. Set job **Python version** to match the cluster (3.11+).
3. Set **Spark** to 3.x and align with `EngineConfig(spark_version="3.5", platform="glue", glue_dpu=...)`.
4. Pass configuration as environment variables or a small `job_params.json` that your job reads and applies via `runtime_conf(EngineConfig(...))`.
5. For API-style workloads, run the FastAPI app on ECS/Fargate or API Gateway + Lambda (with adapter); Glue is best for batch rule evaluation over large tables.

Example parameter file `glue_params.example.json` documents keys you can map to `EngineConfig`.

## `sparkrules-native` (Tier-1 Rust scorer) without PyPI

**`pip install sparkrules-native` and `sparkrules[native]` pulling from PyPI do not work yet** — the wheel is not on the public index. Glue jobs that resolve dependencies only from PyPI will hit **“No matching distribution found”**.

**Practical options:**

1. **CI wheel on S3:** In **Actions → `native` → `wheels`**, download the Linux artifact **`sparkrules-native-ubuntu-22.04-py3.11`** or **`…-py3.12`** (match the job’s Python runtime), upload the `.whl` to S3, and pass it to Glue via **`--extra-py-files s3://bucket/path/sparkrules_native-….whl`** (or the equivalent your template uses). Prefer this over **`--additional-python-modules=sparkrules-native`** until PyPI publishes succeed.
2. **Wait for PyPI:** Maintainer runs **`publish-sparkrules-native.yml`** with **`PYPI_API_TOKEN`** configured; confirm at `https://pypi.org/project/sparkrules-native/` before relying on `pip` in Glue.

Benchmarks that pass **`--additional-python-modules sparkrules-native`** without a private index or S3 wheel URL will fail for the same reason.
