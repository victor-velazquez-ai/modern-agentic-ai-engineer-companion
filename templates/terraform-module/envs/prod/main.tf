# envs/prod/main.tf — the PROD environment: the SAME module as dev, with prod
# values. The only differences between environments live in their tfvars and
# (optionally) provider/region settings — never in duplicated resource code.
#
# Self-contained (provider + variables + module call) so the env is one
# copyable unit. Non-secret values come from terraform.tfvars; secrets are read
# from the environment as TF_VAR_* and never written to disk.

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    # Must match the providers the module declares (modules/service/versions.tf).
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# ▢ TODO: configure the real provider(s) for prod, e.g.:
# provider "aws" {
#   region = var.region
# }

# --- Env inputs (values supplied by terraform.tfvars / TF_VAR_*) -------------

variable "name" {
  description = "Base name for resources in this environment."
  type        = string
  default     = "my-service"
}

variable "instance_count" {
  description = "Number of instances for the prod environment."
  type        = number
  default     = 3
}

variable "tags" {
  description = "Extra tags merged onto every resource."
  type        = map(string)
  default     = {}
}

variable "api_key" {
  description = "Sensitive credential. Supply via `export TF_VAR_api_key=...`, never in tfvars."
  type        = string
  default     = ""
  sensitive   = true
}

# --- Call the reusable module ------------------------------------------------

module "service" {
  source = "../../modules/service"

  name           = var.name
  environment    = "prod"
  instance_count = var.instance_count
  tags           = var.tags

  # Sensitive: read from TF_VAR_api_key, not stored in tfvars or state-by-hand.
  api_key = var.api_key
}

# --- Re-export the module outputs so `terraform output` works at the env -----

output "name_prefix" {
  description = "Resolved resource name prefix for prod."
  value       = module.service.name_prefix
}

output "instance_ids" {
  description = "IDs of the provisioned instances in prod."
  value       = module.service.instance_ids
}
