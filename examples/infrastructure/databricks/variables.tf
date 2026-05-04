variable "prefix" {
  type        = string
  description = "Prefix for Databricks job / cluster naming."
  default     = "sparkrules"
}

variable "create_resources" {
  type        = bool
  description = "If true, create stub resources (requires DATABRICKS_HOST + token)."
  default     = false
}
