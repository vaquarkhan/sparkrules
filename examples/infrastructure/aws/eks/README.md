# AWS EKS — Spark on Kubernetes + SparkRules (Terraform)

Run SparkRules as **Kubernetes SparkApplications** (Spark Operator) or **EMR on EKS** virtual clusters. This folder provides a **minimal EKS cluster** (optional) plus notes for **PySpark images** that include `sparkrules[spark]`.

## Image strategy

- **Base**: official Spark image + `pip install 'sparkrules[spark]'` in a Dockerfile.
- **Rules**: mount **ConfigMap** (DRL text) or pull from **S3** at job start; avoid baking secrets into images.

## Terraform scope

When `create_resources = true`, creates **IAM roles** for the control plane + managed node group pattern (no `aws_eks_cluster` in this slim root), a **`s3-artifacts-aws`** bucket, and **`iam-role-s3-bucket-access-aws`** on the **node role** so driver/executor pods using the node instance profile can **read/write** `s3://…/rules/` and `test-data/`. Production often adds **IRSA** for S3 instead of wide node policy—swap or narrow policies in your live module.

## Required add-ons (manual or separate TF)

- **AWS Load Balancer Controller** if exposing services.
- **Spark Operator** CRDs + `spark-submit` via `SparkApplication`.
- **VPC CNI** defaults; tune IP pool if running many executors.

## References

- Repo `deploy/k8s/` (if present) for sample manifests.
- SparkRules batch path: `apply_drl(df, drl)` inside driver pod.
