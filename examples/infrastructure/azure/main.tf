provider "azurerm" {
  features {}
}

resource "random_id" "storage" {
  count       = var.create_resources ? 1 : 0
  byte_length = 4
}

resource "azurerm_resource_group" "this" {
  count    = var.create_resources ? 1 : 0
  name     = "${var.name_prefix}-rg"
  location = var.location
}

resource "azurerm_storage_account" "rules" {
  count                    = var.create_resources ? 1 : 0
  name                     = "sr${random_id.storage[0].hex}"
  resource_group_name      = azurerm_resource_group.this[0].name
  location                 = azurerm_resource_group.this[0].location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "drl" {
  count                 = var.create_resources ? 1 : 0
  name                  = "rules"
  storage_account_name  = azurerm_storage_account.rules[0].name
  container_access_type = "private"
}

resource "azurerm_storage_container" "testdata" {
  count                 = var.create_resources ? 1 : 0
  name                  = "testdata"
  storage_account_name  = azurerm_storage_account.rules[0].name
  container_access_type = "private"
}
