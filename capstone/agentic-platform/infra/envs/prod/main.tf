# envs/prod/main.tf — the PROD environment: the SAME module as dev, with prod
# values. The only differences between environments live in their tfvars and
# (optionally) provider/region settings — never in duplicated resource code.
#
# Self-contained (provider + variables + module call) so the env is one copyable
# unit. Non-secret values come from terraform.tfvars; secrets are read from the
# environment as TF_VAR_* and never written to disk.

terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

# provider "aws" {
#   region = var.aws_region
# }

# --- Env inputs (values supplied by terraform.tfvars / TF_VAR_*) -------------

variable "aws_region" {
  description = "AWS region for the prod environment."
  type        = string
  default     = "us-east-1"
}

variable "api_desired_count" {
  description = "Number of API tasks in prod (HA)."
  type        = number
  default     = 3
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
  environment = "prod"
  aws_region  = var.aws_region

  # Prod is sized for HA and headroom.
  api_desired_count    = var.api_desired_count
  worker_desired_count = 3
  task_cpu             = 1024
  task_memory          = 2048
  db_instance_class    = "db.r6g.large"
  db_allocated_storage = 100
  redis_node_type      = "cache.r6g.large"

  # Sensitive: read from TF_VAR_db_password, not stored in tfvars.
  db_password = var.db_password

  tags = var.tags
}

# --- Re-export module outputs so `terraform output` works at the env ---------

output "name_prefix" {
  description = "Resolved resource name prefix for prod."
  value       = module.platform.name_prefix
}

output "artifacts_bucket" {
  description = "S3 artifacts bucket for prod."
  value       = module.platform.artifacts_bucket
}
