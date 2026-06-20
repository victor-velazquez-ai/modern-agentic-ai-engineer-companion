# envs/dev/main.tf — the DEV environment: calls the reusable module with dev
# values. Environments hold *values*; the module holds *behavior*. To change
# what the infra does, edit the module; to change dev's sizing/naming, edit
# here or dev's terraform.tfvars.
#
# This file is self-contained (provider + variables + module call) so the env
# is a single, copyable unit. Non-secret values are set in terraform.tfvars;
# secrets are read from the environment as TF_VAR_* and never written to disk.

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

# ▢ TODO: configure the real provider(s) for this environment, e.g.:
# provider "aws" {
#   region = var.region   # often a var so dev/prod can differ
# }

# --- Env inputs (values supplied by terraform.tfvars / TF_VAR_*) -------------

variable "name" {
  description = "Base name for resources in this environment."
  type        = string
  default     = "my-service"
}

variable "instance_count" {
  description = "Number of instances for the dev environment."
  type        = number
  default     = 1
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
  environment    = "dev"
  instance_count = var.instance_count
  tags           = var.tags

  # Sensitive: read from TF_VAR_api_key, not stored in tfvars or state-by-hand.
  api_key = var.api_key
}

# --- Re-export the module outputs so `terraform output` works at the env -----

output "name_prefix" {
  description = "Resolved resource name prefix for dev."
  value       = module.service.name_prefix
}

output "instance_ids" {
  description = "IDs of the provisioned instances in dev."
  value       = module.service.instance_ids
}
