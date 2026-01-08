terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.57.0"
    }
  }

  backend "azurerm" {
    container_name = "terraform"
    key            = "state"
    # resource_group_name  = ""
    # storage_account_name = ""
  }
}

provider "azurerm" {
  features {}
}

variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "cluster_name" { type = string }
variable "acr_name" { type = string }

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

module "aks" {
  source              = "./modules/aks"
  location            = var.location
  resource_group_name = var.resource_group_name
  cluster_name        = var.cluster_name
}

module "acr" {
  source              = "./modules/acr"
  location            = var.location
  resource_group_name = var.resource_group_name
  acr_name            = var.acr_name
  kubelet_identity    = module.aks.kubelet_identity
}

output "resource_group" { value = azurerm_resource_group.rg.name }
output "cluster_name" { value = var.cluster_name }
output "registry_name" { value = module.acr.registry_name }
output "registry_login_server" { value = module.acr.login_server }
