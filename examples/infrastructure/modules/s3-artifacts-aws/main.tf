resource "aws_s3_bucket" "artifacts" {
  count  = var.create ? 1 : 0
  bucket = "${var.name_prefix}-artifacts-${var.account_id}"

  force_destroy = var.force_destroy

  tags = {
    Purpose    = "sparkrules-artifacts"
    ManagedBy  = "terraform"
    Module     = "s3-artifacts-aws"
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  count  = var.create ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  count  = var.create && var.enable_versioning ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  count  = var.create ? 1 : 0
  bucket = aws_s3_bucket.artifacts[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
