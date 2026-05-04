variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "sparkrules-glue"
}

variable "create_resources" {
  type    = bool
  default = false
}
