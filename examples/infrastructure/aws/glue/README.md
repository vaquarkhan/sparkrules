# AWS Glue — Spark ETL with SparkRules (Terraform)

Glue 4.x / 5.x runs Spark; install **SparkRules** via **extra Python modules** or a **wheel** on S3 referenced in `additional_python_modules` / `--extra-py-files`.

## Glue job shape

1. **Script** on S3: PySpark entry that reads your tables/stream, calls `sparkrules.spark.apply_drl` or `SparkRuleExecutor`.
2. **Connections** for VPC + JDBC/Kafka as needed (Glue connection → subnet + SG).
3. **IAM role** allowing Glue to read/write S3, Glue catalog, and any Kafka via VPC.

## Terraform in this folder

Creates a **Glue job IAM role**, a **private workspace S3 bucket** (SSE-S3, public access block), and a **Terraform-managed inline policy** so that role can **read/write** that bucket (`iam-role-s3-bucket-access-aws`). Upload scripts, DRL under **`rules/`**, test payloads under **`test-data/`** after `apply`. Glue service + VPC policies are still added when you define the actual `aws_glue_job`.

## SparkRules packaging

- Build a **wheel** in CI: `pip wheel sparkrules[spark] -w dist/`, upload to `s3://.../wheels/`.
- Or use AWS CodeArtifact / private PyPI with Glue’s `--additional-python-modules`.

## Variables

See `variables.tf`. Tune `glue_version`, `worker_type`, and `number_of_workers` in an expanded `aws_glue_job` block (comment stubs in `main.tf`).
