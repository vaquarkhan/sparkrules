variable "location" {
  type    = string
  default = "eastus"
}

variable "name_prefix" {
  type    = string
  default = "sparkrules"
}

variable "create_resources" {
  type    = bool
  default = false
}
