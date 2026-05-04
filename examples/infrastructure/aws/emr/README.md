# AWS EMR — Spark + SparkRules (Terraform)

This stack composes **reusable modules** under **[../../modules/README.md](../../modules/README.md)**:

- **`s3-artifacts-aws`** — private, SSE-S3, versioned artifact bucket  
- **`emr-ec2-roles-aws`** — EC2 instance profile for EMR workers  
- **`iam-role-s3-bucket-access-aws`** — **inline IAM** so the EMR EC2 role can **list/read/write/delete** objects in that bucket (same bucket for **rules** and **test data**, different key prefixes)

After apply, use outputs `sparkrules_s3_rules_prefix` and `sparkrules_s3_test_data_prefix` (e.g. `aws s3 cp policy.drl …/rules/` and sample facts under `…/test-data/`). Terraform does **not** upload files; it provisions **IAM + S3** only.

Use it as a **bootstrap** for `spark-submit` jobs that call `sparkrules.spark.apply_drl`. See **`terraform.tfvars.example`** for variables.

> **Browser Workbench login** is optional and **disabled in the static UI shell by default** (`WORKBENCH_LOGIN_UI_ENABLED = false` in `index.html`). Use **`SPARKRULES_API_KEY`** or leave **`SPARKRULES_WORKBENCH_AUTH`** unset for batch-only clusters.

## What you still wire by hand

- **VPC subnets** with routes to Kafka / data sources (pass `subnet_ids` when `create_resources = true`).
- **EMR cluster** resource (version-pin `release_label`, master/core instance groups, auto-scaling).
- **Bootstrap action** to `pip install 'sparkrules[spark]==<version>'` on all nodes (same path on workers).
- **Step** or **fleet** that runs your PySpark module calling `apply_drl`.

## Environment (job)

| Variable | Example |
|----------|---------|
| `SPARKRULES_DRL_PATH` | `s3://bucket/rules/policy.drl` mounted or pulled in `driver` |
| Packages | `org.apache.spark:spark-sql-kafka-0-10` for streaming sources |

## Files

| File | Purpose |
|------|---------|
| `versions.tf` | Terraform + AWS provider pins |
| `variables.tf` | `aws_region`, `name_prefix`, `create_resources`, `artifacts_force_destroy`, etc. |
| `main.tf` | **`artifacts`** + **`emr_ec2`** + **`emr_artifacts_s3`** (S3 IAM on the instance profile) |
| `outputs.tf` | Instance profile, bucket, **`s3://…/rules/`** and **`…/test-data/`** prefixes |
| `terraform.tfvars.example` | Copy to `terraform.tfvars` and edit for your account |
| `backend.tf.example` | Optional: copy to `backend.tf` for S3 remote state + DynamoDB lock (team applies) |

## Apply (dev)

```bash
terraform init
export TF_VAR_name_prefix="myorg-dev"
terraform apply
```

See `deploy/emr` in the repo root if present for additional notes; otherwise treat this folder as the canonical **IaC starter** under `examples/`.
