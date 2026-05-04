output "resource_group" {
  value = var.create_resources ? azurerm_resource_group.this[0].name : null
}

output "storage_account" {
  value = var.create_resources ? azurerm_storage_account.rules[0].name : null
}

output "rules_container" {
  value = var.create_resources ? azurerm_storage_container.drl[0].name : null
}
