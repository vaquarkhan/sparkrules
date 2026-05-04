provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

module "artifacts" {
  source = "../../modules/s3-artifacts-aws"

  create        = var.create_resources
  name_prefix   = var.name_prefix
  account_id    = local.account_id
  force_destroy = var.artifacts_force_destroy
}

module "emr_ec2" {
  source = "../../modules/emr-ec2-roles-aws"

  create      = var.create_resources
  name_prefix = var.name_prefix
}

# IAM: EMR EC2 instance profile can read/write SparkRules artifacts (DRL, packs, test facts).
module "emr_artifacts_s3" {
  count  = var.create_resources ? 1 : 0
  source = "../../modules/iam-role-s3-bucket-access-aws"

  create      = true
  role_name   = module.emr_ec2.ec2_role_name
  policy_name = "${var.name_prefix}-sparkrules-artifacts-s3"
  bucket_arn  = module.artifacts.bucket_arn
}
