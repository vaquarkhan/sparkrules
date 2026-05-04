# Terraform modules (SparkRules infrastructure)

Small, composable building blocks for **artifacts storage** and **compute IAM** on AWS. Use them from the **root examples** under `../aws/*`, `../gcp`, or your own live root module.

| Module | Cloud | Purpose |
|--------|-------|---------|
| [s3-artifacts-aws](s3-artifacts-aws/) | AWS | Private **S3** bucket (encryption, public access block, optional versioning) |
| [emr-ec2-roles-aws](emr-ec2-roles-aws/) | AWS | **EMR EC2** IAM role + instance profile |
| [iam-role-s3-bucket-access-aws](iam-role-s3-bucket-access-aws/) | AWS | **Inline IAM policy** on a role for **ListBucket + object R/W** on one bucket (use key prefixes `rules/`, `test-data/` instead of a second bucket) |

**Glue / EKS** roots now attach the same **IAM + S3** pattern where a compute role and bucket are defined in Terraform. **GCP** uses `roles/storage.objectUser` on the artifacts bucket for Dataproc SA; **Azure** adds **`rules`** and **`testdata`** containers (assign **Storage Blob Data** roles to your workload identity outside Terraform or extend this root).

See **[docs/INFRASTRUCTURE_TERRAFORM.md](../../../docs/INFRASTRUCTURE_TERRAFORM.md)** for end-to-end apply order and prod notes.
