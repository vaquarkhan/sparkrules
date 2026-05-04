variable "project_id" {
  type        = string
  description = "GCP project ID."
  default     = ""
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "name_prefix" {
  type    = string
  default = "sparkrules"
}

variable "create_resources" {
  type    = bool
  default = false
}
