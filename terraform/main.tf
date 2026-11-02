terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  # For a team project, move state to Azure Storage instead of your laptop:
  # backend "azurerm" {
  #   resource_group_name  = "tfstate-rg"
  #   storage_account_name = "<unique-name>"
  #   container_name       = "tfstate"
  #   key                  = "hedge-fund.tfstate"
  # }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# ── Option A: AKS (Kubernetes) ───────────────────────────────────────────────
resource "azurerm_kubernetes_cluster" "aks" {
  count               = var.deploy_aks ? 1 : 0
  name                = "${var.prefix}-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = "${var.prefix}-aks"
  sku_tier            = "Free"

  default_node_pool {
    name       = "system"
    node_count = var.aks_node_count
    vm_size    = var.aks_vm_size
  }

  identity { type = "SystemAssigned" }

  tags = var.tags
}

# ── Option B: Azure App Service (single container, cheapest) ─────────────────
resource "azurerm_service_plan" "plan" {
  count               = var.deploy_app_service ? 1 : 0
  name                = "${var.prefix}-plan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = var.app_service_sku
  tags                = var.tags
}

resource "azurerm_linux_web_app" "app" {
  count               = var.deploy_app_service ? 1 : 0
  name                = "${var.prefix}-app"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.plan[0].id
  https_only          = true

  site_config {
    always_on         = var.app_service_sku != "F1"
    websockets_enabled = true          # Streamlit needs websockets
    health_check_path = "/_stcore/health"
    application_stack {
      docker_image_name   = "${var.image_repository}:${var.image_tag}"
      docker_registry_url = "https://ghcr.io"
    }
  }

  app_settings = {
    WEBSITES_PORT = "8501"
  }

  tags = var.tags
}
