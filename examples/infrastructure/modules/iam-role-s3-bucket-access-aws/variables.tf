variable "create" {
  type        = bool
  description = "If false, no IAM policy resource is created."
}

variable "role_name" {
  type        = string
  description = "IAM role name to attach the inline policy to (e.g. EMR EC2, Glue job, EKS node)."
}

variable "policy_name" {
  type        = string
  description = "Suffix-unique policy name on the role."
}

variable "bucket_arn" {
  type        = string
  description = "S3 bucket ARN (not object ARNs). Objects use bucket_arn/* ."
}
