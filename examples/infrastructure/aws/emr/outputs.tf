output "account_id" {
  value = local.account_id
}

output "artifact_bucket_id" {
  description = "S3 bucket for DRL / wheels / logs."
  value       = module.artifacts.bucket_id
}

output "artifact_bucket_arn" {
  value = module.artifacts.bucket_arn
}

output "emr_ec2_role_arn" {
  value = module.emr_ec2.ec2_role_arn
}

output "emr_instance_profile_name" {
  description = "Pass to EMR instance groups / serverless job role wiring."
  value       = module.emr_ec2.instance_profile_name
}

output "sparkrules_s3_rules_prefix" {
  description = "Upload DRL / rule packs under this prefix (aws s3 cp ...)."
  value       = var.create_resources ? "s3://${module.artifacts.bucket_id}/rules/" : null
}

output "sparkrules_s3_test_data_prefix" {
  description = "Sample facts / Parquet for batch jobs (not a separate bucket by default)."
  value       = var.create_resources ? "s3://${module.artifacts.bucket_id}/test-data/" : null
}
