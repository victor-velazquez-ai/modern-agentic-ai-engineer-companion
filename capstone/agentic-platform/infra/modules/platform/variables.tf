# variables.tf — the platform module's TYPED INPUT CONTRACT.
#
# Every variable has a `type` and a `description`. Defaults are provided only
# where a value is genuinely safe to omit. Secrets are marked `sensitive = true`
# and must be supplied via `TF_VAR_*` / a secrets backend — never in `*.tfvars`.
#
# This module stands up the platform's AWS target (Appendix C): VPC, an
# ECS/Fargate service for the api + worker image, an RDS Postgres (pgvector)
# instance, an ElastiCache Redis (Celery broker + cache), and an S3 bucket
# (artifacts / document uploads).

# --- Identity / required inputs ---------------------------------------------

variable "name" {
  description = "Base name for resources this module creates (DNS-safe: lowercase, hyphens)."
  type        = string
  default     = "agentic-platform"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}[a-z0-9]$", var.name))
    error_message = "name must be 3-40 chars, lowercase alphanumeric or hyphens, and start with a letter."
  }
}

variable "environment" {
  description = "Deployment environment this instance belongs to."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region to deploy into (used once the aws provider is enabled)."
  type        = string
  default     = "us-east-1"
}

# --- Networking (VPC) -------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "az_count" {
  description = "Number of availability zones to spread subnets across (HA)."
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 1 && var.az_count <= 3
    error_message = "az_count must be between 1 and 3."
  }
}

# --- Compute (ECS / Fargate) ------------------------------------------------

variable "service_image" {
  description = "Container image (api + worker share one image; see ../../../Dockerfile)."
  type        = string
  default     = "agentic-platform:latest"
}

variable "api_desired_count" {
  description = "Number of Fargate tasks running the API."
  type        = number
  default     = 2

  validation {
    condition     = var.api_desired_count >= 1 && var.api_desired_count <= 50
    error_message = "api_desired_count must be between 1 and 50."
  }
}

variable "worker_desired_count" {
  description = "Number of Fargate tasks running the Celery worker."
  type        = number
  default     = 1

  validation {
    condition     = var.worker_desired_count >= 0 && var.worker_desired_count <= 50
    error_message = "worker_desired_count must be between 0 and 50."
  }
}

variable "task_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU)."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024
}

# --- Data layer (RDS Postgres + ElastiCache Redis) --------------------------

variable "db_instance_class" {
  description = "RDS instance class for Postgres (pgvector)."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "db_password" {
  description = "Postgres master password. Supply via TF_VAR_db_password, NOT tfvars."
  type        = string
  default     = ""
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type (Celery broker + result backend + cache)."
  type        = string
  default     = "cache.t4g.micro"
}

# --- Object storage (S3) ----------------------------------------------------

variable "artifacts_bucket_name" {
  description = "S3 bucket for document uploads / build artifacts. Empty = derive from name+env."
  type        = string
  default     = ""
}

# --- Tagging ----------------------------------------------------------------

variable "tags" {
  description = "Tags applied to every resource the module creates."
  type        = map(string)
  default     = {}
}
