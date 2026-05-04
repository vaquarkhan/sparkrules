output "bucket_id" {
  value = var.create ? aws_s3_bucket.artifacts[0].id : null
}

output "bucket_arn" {
  value = var.create ? aws_s3_bucket.artifacts[0].arn : null
}

output "bucket_domain_name" {
  value = var.create ? aws_s3_bucket.artifacts[0].bucket_domain_name : null
}
