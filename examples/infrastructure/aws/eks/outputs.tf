output "eks_cluster_role_arn" {
  value = var.create_resources ? aws_iam_role.eks_cluster[0].arn : null
}

output "eks_node_role_arn" {
  value = var.create_resources ? aws_iam_role.eks_node[0].arn : null
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "artifact_bucket_id" {
  description = "S3 bucket for DRL, packs, test data (Spark on EKS node role has RW)."
  value       = module.artifacts.bucket_id
}

output "sparkrules_s3_rules_prefix" {
  value = var.create_resources ? "s3://${module.artifacts.bucket_id}/rules/" : null
}
