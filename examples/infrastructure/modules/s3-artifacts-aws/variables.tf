variable "create" {
  type        = bool
  description = "If false, no resources (compose-only / validate)."
}

variable "name_prefix" {
  type = string
}

variable "account_id" {
  type = string
}

variable "force_destroy" {
  type        = bool
  description = "Allow bucket destroy with objects (dev only)."
  default     = false
}

variable "enable_versioning" {
  type    = bool
  default = true
}
