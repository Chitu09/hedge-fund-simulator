variable "subscription_id" {
  type        = string
  description = "Azure subscription ID (az account show --query id -o tsv)"
}

variable "prefix" {
  type    = string
  default = "hfsim"
}

variable "location" {
  type    = string
  default = "centralindia"
}

variable "deploy_aks" {
  type    = bool
  default = true
}

variable "aks_node_count" {
  type    = number
  default = 1
}

variable "aks_vm_size" {
  type    = string
  default = "Standard_B2s"
}

variable "deploy_app_service" {
  type    = bool
  default = false
}

variable "app_service_sku" {
  type    = string
  default = "B1"
}

variable "image_repository" {
  type    = string
  default = "YOUR_GITHUB_USERNAME/hedge-fund-simulator"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "tags" {
  type = map(string)
  default = {
    project = "multi-strategy-hedge-fund-simulator"
    managed = "terraform"
  }
}
