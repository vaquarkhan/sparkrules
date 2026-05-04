variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "sparkrules-eks"
}

variable "create_resources" {
  type        = bool
  description = "Creates IAM roles for EKS control plane and nodes (add VPC + aws_eks_cluster separately or via a module)."
  default     = false
}
