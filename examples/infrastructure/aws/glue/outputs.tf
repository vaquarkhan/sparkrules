output "glue_role_arn" {
  value = var.create_resources ? aws_iam_role.glue[0].arn : null
}

output "workspace_bucket" {
  value = var.create_resources ? aws_s3_bucket.glue_workspace[0].bucket : null
}

output "sparkrules_s3_upload_prefixes" {
  description = "Use keys under these prefixes (same bucket): rules/, test-data/, glue-assets/."
  value       = var.create_resources ? "s3://${aws_s3_bucket.glue_workspace[0].bucket}/rules/ | .../test-data/ | .../glue-assets/" : null
}
