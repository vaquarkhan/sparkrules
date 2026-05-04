# Infrastructure as code (Terraform)

**Production-grade building blocks** for SparkRules on cloud data platforms: **reusable modules**, **root stacks** per service, **`terraform.tfvars.example` in each root**, and an **AWS EMR deployment runbook**.

| Layer | Location | Contents |
|-------|----------|----------|
| **Modules** | [modules/](modules/README.md) | **`s3-artifacts-aws`** (SSE-S3, public access block, versioning), **`emr-ec2-roles-aws`** (EMR worker IAM + instance profile) |
| **AWS EMR** (composed) | [aws/emr/](aws/emr/) | Uses modules; **`terraform.tfvars.example`**; optional **`backend.tf.example`** |
| **AWS Glue** | [aws/glue/](aws/glue/) | Glue service IAM + workspace bucket; **`terraform.tfvars.example`** |
| **AWS EKS** | [aws/eks/](aws/eks/) | Cluster + node IAM; **`terraform.tfvars.example`** |
| **Databricks** | [databricks/](databricks/) | Provider stubs; **`terraform.tfvars.example`** |
| **GCP** | [gcp/](gcp/) | Service account + GCS bucket; **`terraform.tfvars.example`** |
| **Azure** | [azure/](azure/) | RG + storage; **`terraform.tfvars.example`** |
| **Runbook** | [deployments/aws-emr-production/](deployments/aws-emr-production/README.md) | End-to-end EMR + artifacts checklist |

**Documentation:** [docs/INFRASTRUCTURE_TERRAFORM.md](../../docs/INFRASTRUCTURE_TERRAFORM.md) (design, validate-only workflow, **cost / apply / destroy for experiments**, relation to Workbench).

## Workbench browser login

The shipped API static shell **hides the Workbench sign-in UI by default** so local use does not depend on `SPARKRULES_WORKBENCH_AUTH`. See [docs/WORKBENCH_LOGIN.md](../../docs/WORKBENCH_LOGIN.md). Clusters using Terraform here are typically **batch-only**; use **`SPARKRULES_API_KEY`** when calling the REST API if needed.

## Shared operator steps (all platforms)

1. Install matching **`sparkrules[spark]`** on driver and executors (same minor Python as CI).
2. Ship DRL or compiled pack via object storage; use `SPARKRULES_MAX_RULEPACK_BYTES` and checkpoint paths only for this job.
3. Prefer **broadcast** of compiled rule packs on large clusters (`sparkrules/transport/broadcaster.py`).

## Validate without applying

```bash
cd examples/infrastructure/aws/emr
terraform init -backend=false
terraform validate
```

Set **`create_resources = true`** in `terraform.tfvars` only in a **dev/sandbox account** with credentials configured. Use a **remote backend** (S3 + lock) for shared teams—see **`backend.tf.example`** in `aws/emr/`.

**Experiments:** `terraform plan` before every apply; **`terraform destroy`** (or plan-destroy) when finished so S3/IAM resources do not linger. See the **Cost, apply, and destroy** section in [docs/INFRASTRUCTURE_TERRAFORM.md](../../docs/INFRASTRUCTURE_TERRAFORM.md).
