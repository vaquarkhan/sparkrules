output "artifacts_bucket" {
  value = var.create_resources && var.project_id != "" ? google_storage_bucket.artifacts[0].name : null
}

output "service_account_email" {
  value = var.create_resources && var.project_id != "" ? google_service_account.dataproc_rules[0].email : null
}
