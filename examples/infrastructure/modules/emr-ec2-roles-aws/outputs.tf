output "ec2_role_arn" {
  value = var.create ? aws_iam_role.emr_ec2[0].arn : null
}

output "ec2_role_name" {
  value = var.create ? aws_iam_role.emr_ec2[0].name : null
}

output "instance_profile_arn" {
  value = var.create ? aws_iam_instance_profile.emr_ec2[0].arn : null
}

output "instance_profile_name" {
  value = var.create ? aws_iam_instance_profile.emr_ec2[0].name : null
}
