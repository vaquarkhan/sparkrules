data "aws_partition" "current" {}

data "aws_iam_policy_document" "emr_ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.${data.aws_partition.current.dns_suffix}"]
    }
  }
}

resource "aws_iam_role" "emr_ec2" {
  count              = var.create ? 1 : 0
  name               = "${var.name_prefix}-emr-ec2"
  assume_role_policy = data.aws_iam_policy_document.emr_ec2_assume.json

  tags = {
    Purpose = "sparkrules-emr-ec2"
    Module  = "emr-ec2-roles-aws"
  }
}

resource "aws_iam_instance_profile" "emr_ec2" {
  count = var.create ? 1 : 0
  name  = "${var.name_prefix}-emr-ec2"
  role  = aws_iam_role.emr_ec2[0].name
}
