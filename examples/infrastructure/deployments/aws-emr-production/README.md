# Deployment example: AWS EMR + SparkRules (production-style)

End-to-end **order of operations** for a team running PySpark + SparkRules on EMR.

## 1. Bootstrap artifacts & IAM

From the repo:

```bash
cd examples/infrastructure/aws/emr
cp terraform.tfvars.example terraform.tfvars
# Edit: create_resources = true, name_prefix, region
terraform init
terraform apply
```

Note **outputs**: artifact bucket, instance profile, **`sparkrules_s3_rules_prefix`** / **`sparkrules_s3_test_data_prefix`** (where to `aws s3 cp` DRL and sample facts).

## 2. Remaining IAM (EMR service)

The root **`aws/emr`** stack already attaches **Terraform-managed S3 access** to the EMR EC2 role (`iam-role-s3-bucket-access-aws`: list + object read/write on the artifacts bucket). You still attach **EMR service** policies when defining the cluster, for example:

- **`AmazonElasticMapReduceforEC2Role`** (and related) — usually when creating the EMR cluster resource.
- **KMS decrypt** if you switch the bucket to SSE-KMS.

You do **not** need a separate console-only “S3 read” on the artifact bucket for SparkRules files; upload with your operator role or CI, run with the instance profile.

## 3. Cluster or job

- **EMR on EC2**: pass instance profile; bootstrap pip install `sparkrules[spark]==…`  
- **EMR Serverless**: align job role with the same S3/KMS permissions

## 4. Rules & secrets

- Store DRL under `s3://<artifact-bucket>/rules/…`  
- Never embed API keys in DRL; use **Secrets Manager** + bootstrap script for `SPARKRULES_*` if needed.

## 5. Workbench

The browser Workbench is **independent** of EMR. Optional **`SPARKRULES_API_KEY`** on the API pod; **browser login UI** is off by default in the shipped shell (`WORKBENCH_LOGIN_UI_ENABLED`).

## Example tfvars

Use `../../aws/emr/terraform.tfvars.example` as the template; keep a **per-env** `terraform.tfvars` outside VCS or in a private ops repo.
