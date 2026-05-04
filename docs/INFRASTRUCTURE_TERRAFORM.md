# Infrastructure as code (Terraform) — SparkRules

The **[examples/infrastructure/](../examples/infrastructure/)** tree ships **production-oriented** Terraform layouts: **modules** (reusable) + **root examples** per cloud (AWS EMR/Glue/EKS, Databricks, GCP, Azure) with **`terraform.tfvars.example`** files.

## What you get

| Layer | Contents |
|-------|-----------|
| **Modules** | `s3-artifacts-aws`, `emr-ec2-roles-aws`, **`iam-role-s3-bucket-access-aws`** (attach least-privilege S3 R/W on one bucket to a **named IAM role**) |
| **Roots** | **EMR**, **EKS**, and **Glue** compose **bucket + role + IAM policy** in Terraform so you can **upload** DRL/test data and **run** jobs without hand-attaching policies in the console. Prefixes: `rules/`, `test-data/` (one bucket). |
| **Deployments** | `examples/infrastructure/deployments/aws-emr-production` — runbook-style **end-to-end** checklist |
| **Examples** | `*.tfvars.example` — copy to `terraform.tfvars`, set `create_resources`, never commit secrets |

## Validate without AWS charges

```bash
cd examples/infrastructure/aws/emr
terraform init -backend=false
terraform validate
```

## Cost, apply, and destroy (experiments)

These examples create **real cloud resources** when `create_resources = true`. **Always assume apply may incur charges** (object storage, API calls, data transfer, and any compute you add outside these roots). Tags on resources help cost allocation; turn on **billing alerts** in your cloud console for dev accounts.

### Before you apply

1. Work in a **sandbox / dev subscription** with spending limits where possible.
2. Run **`terraform plan`** and read the diff (IAM roles, S3 buckets, policies). No plan, no apply.
3. Copy **`terraform.tfvars.example`** → **`terraform.tfvars`**; set **`create_resources = true`** only when you intend to provision.
4. Prefer **`terraform plan -out=tfplan`** then **`terraform apply tfplan`** for reproducible applies.

### Apply (run)

From the chosen root (example: EMR stack):

```bash
cd examples/infrastructure/aws/emr
terraform init
# Edit terraform.tfvars: create_resources = true, name_prefix, aws_region, etc.
terraform plan -out=tfplan
terraform apply tfplan
```

Record **outputs** (bucket names, role ARNs) for your jobs; do not commit **`terraform.tfvars`** or plan files with secrets.

### Destroy and cleanup (required for experiments)

**Tear down resources when the experiment is done** so idle buckets, roles, and attachments do not accumulate cost or security sprawl.

1. **Empty S3 buckets** if your provider refuses to delete non-empty buckets. Our AWS **artifacts** module supports **`force_destroy`** on the bucket (set via **`artifacts_force_destroy`** in `aws/emr`) for **dev-only** convenience so **`terraform destroy`** can delete the bucket after objects are removed or when `force_destroy` is enabled (use only in non-prod).
2. From the same directory and state as the apply:

   ```bash
   terraform plan -destroy -out=destroy.tfplan
   terraform apply destroy.tfplan
   ```

   Or interactively: **`terraform destroy`** (confirm when prompted).

3. **Verify** in the console or CLI that buckets, IAM roles, and policies are gone in the intended region/account.
4. If you used a **remote state** backend, consider whether to remove or retain the **state object** per your team policy after destroy.

**Rule of thumb:** treat **`terraform destroy`** as part of the same “experiment” as **`terraform apply`**—especially for S3 + IAM stacks where ongoing storage and stale roles are easy to forget.

## Design principles

1. **`create_resources = false`** by default — safe CI and local validate.  
2. **State** — use a remote backend (S3 + DynamoDB lock on AWS) in real environments; see `backend.tf.example` patterns in your org.  
3. **Least privilege** — module outputs ARNs; attach fine-grained S3/KMS policies in a **wrapper** module or manually.  
4. **SparkRules** runs **on the cluster** via `pip install sparkrules[spark]` — Terraform provisions **S3 + IAM**; **`terraform apply` does not upload** DRL or facts (use `aws s3 cp`, CI, or your pipeline after the bucket exists).  
5. **No second “test bucket” by default** — use **`…/test-data/`** keys next to **`…/rules/`** unless compliance requires isolation (then add another `s3-artifacts` module + second `iam-role-s3-bucket-access` attachment).

## Relation to Workbench UI

Terraform **does not** deploy the FastAPI Workbench. Run Workbench via **`pip install sparkrules[api]`** (see `AGENTS.md`). Optional **`SPARKRULES_WORKBENCH_AUTH`** protects the API; the **browser login overlay is disabled by default** in the shipped static shell — re-enable by setting **`WORKBENCH_LOGIN_UI_ENABLED = true`** in `src/sparkrules/api/static/workbench/index.html` when you are ready.
