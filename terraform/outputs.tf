output "resource_group" {
  value = azurerm_resource_group.rg.name
}

output "aks_cluster_name" {
  value = var.deploy_aks ? azurerm_kubernetes_cluster.aks[0].name : null
}

output "aks_get_credentials" {
  value = var.deploy_aks ? "az aks get-credentials -g ${azurerm_resource_group.rg.name} -n ${azurerm_kubernetes_cluster.aks[0].name}" : null
}

output "app_service_url" {
  value = var.deploy_app_service ? "https://${azurerm_linux_web_app.app[0].default_hostname}" : null
}
