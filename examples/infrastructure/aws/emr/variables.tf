variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "sparkrules-emr"
}

variable "create_resources" {
  type        = bool
  description = "If true, create S3 + IAM via modules."
  default     = false
}

variable "artifacts_force_destroy" {
  type        = bool
  description = "Dev only: empty bucket on terraform destroy."
  default     = false
}
