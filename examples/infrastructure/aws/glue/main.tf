provider "aws" {
  region = var.aws_region
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "glue_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

resource "aws_iam_role" "glue" {
  count              = var.create_resources ? 1 : 0
  name               = "${var.name_prefix}-job-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume.json
  tags = {
    Purpose = "sparkrules-glue"
  }
}

# Attach AWS managed Glue service policies via console, or add policy ARNs (e.g. Glue + CloudWatch) in this root.

resource "aws_s3_bucket" "glue_workspace" {
  count  = var.create_resources ? 1 : 0
  bucket = "${var.name_prefix}-workspace-${local.account_id}"
  tags = {
    Purpose = "sparkrules-glue-scripts-wheels"
  }
}

resource "aws_s3_bucket_public_access_block" "glue_workspace" {
  count  = var.create_resources ? 1 : 0

  bucket                  = aws_s3_bucket.glue_workspace[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "glue_workspace" {
  count  = var.create_resources ? 1 : 0
  bucket = aws_s3_bucket.glue_workspace[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Terraform-managed IAM: Glue job role can read/write the workspace bucket (scripts, DRL, test JSON).
module "glue_workspace_s3_access" {
  count  = var.create_resources ? 1 : 0
  source = "../../modules/iam-role-s3-bucket-access-aws"

  create      = true
  role_name   = aws_iam_role.glue[0].name
  policy_name = "${var.name_prefix}-glue-ws-s3"
  bucket_arn  = aws_s3_bucket.glue_workspace[0].arn
}
