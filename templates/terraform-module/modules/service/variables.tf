# variables.tf — the module's TYPED INPUT CONTRACT.
#
# Every variable has a `type` and a `description`. Provide a `default` only when
# a value is genuinely safe to omit; leave required inputs without a default so
# Terraform errors loudly if a caller forgets them. Secrets are marked
# `sensitive = true` and must be supplied via `TF_VAR_*` / a secrets backend —
# never written into `*.tfvars`.

# --- Identity / required inputs ---------------------------------------------

variable "name" {
  description = "Base name for the resources this module creates (DNS-safe: lowercase, hyphens)."
  type        = string

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

# --- Optional inputs with safe defaults -------------------------------------

variable "instance_count" {
  description = "Number of service instances / replicas to provision."
  type        = number
  default     = 1

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 100
    error_message = "instance_count must be between 1 and 100."
  }
}

variable "tags" {
  description = "Tags/labels applied to every resource the module creates."
  type        = map(string)
  default     = {}
}

# --- Example: a sensitive input (NEVER put its value in *.tfvars) ------------
# Supply this via the environment: `export TF_VAR_api_key=...` (or a secrets
# backend). The default "" lets the module `plan` without it; make it required
# (remove the default) once a real resource consumes it.

variable "api_key" {
  description = "Sensitive credential consumed by the service. Supply via TF_VAR_api_key, not tfvars."
  type        = string
  default     = ""
  sensitive   = true
}

# ▢ TODO: add the real inputs your resources need (vpc_id, subnet_ids,
#         instance_type, image, db_password [sensitive], ...). Keep each one
#         typed + described, and mark secrets `sensitive = true`.
