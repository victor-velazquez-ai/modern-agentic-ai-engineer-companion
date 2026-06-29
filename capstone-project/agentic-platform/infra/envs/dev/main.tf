# envs/dev/main.tf — the DEV environment: calls the reusable platform module
# with dev values. Environments hold *values*; the module holds *behavior*.
#
# Self-contained (provider + variables + module call) so the env is one copyable
# unit. Non-secret values live in terraform.tfvars; secrets are read from the
# environment as TF_VAR_* and never written to disk.

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    # Must match the providers the module declares (modules/platform/versions.tf).
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# Configure the real provider once the module's aws provider is enabled:
# provider "aws" {
#   region = var.aws_region
# }

# --- Env inputs (values supplied by terraform.tfvars / TF_VAR_*) -------------

variable "aws_region" {
  description = "AWS region for the dev environment."
  type        = string
  default     = "us-east-1"
}

variable "api_desired_count" {
  description = "Number of API tasks in dev."
  type        = number
  default     = 1
}

variable "db_password" {
  description = "Postgres master password. Supply via `export TF_VAR_db_password=...`."
  type        = string
  default     = ""
  sensitive   = true
}

variable "tags" {
  description = "Extra tags merged onto every resource."
  type        = map(string)
  default     = {}
}

# --- Call the reusable module ------------------------------------------------

module "platform" {
  source = "../../modules/platform"

  name        = "agentic-platform"
  environment = "dev"
  aws_region  = var.aws_region

  # Dev is small and single-instance to keep cost near zero.
  api_desired_count    = var.api_desired_count
  worker_desired_count = 1
  db_instance_class    = "db.t4g.micro"
  redis_node_type      = "cache.t4g.micro"

  # Sensitive: read from TF_VAR_db_password, not stored in tfvars.
  db_password = var.db_password

  tags = var.tags
}

# --- Re-export module outputs so `terraform output` works at the env ---------

output "name_prefix" {
  description = "Resolved resource name prefix for dev."
  value       = module.platform.name_prefix
}

output "artifacts_bucket" {
  description = "S3 artifacts bucket for dev."
  value       = module.platform.artifacts_bucket
}
