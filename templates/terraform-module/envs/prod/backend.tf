# envs/prod/backend.tf — REMOTE STATE backend (commented stub).
#
# Prod state MUST be remote, versioned, locked, and encrypted — and NEVER
# committed (state can contain secrets; see the repo .gitignore for *.tfstate).
# Use a SEPARATE state path/workspace from dev so the two environments can never
# clobber each other.
#
# ▢ TODO: pick ONE backend, uncomment it, fill the placeholders, then run
#         `terraform init -migrate-state`.
#
# --- AWS S3 + DynamoDB lock ---------------------------------------------------
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE-tfstate-bucket"    # ▢ TODO: existing, versioned bucket
#     key            = "envs/prod/terraform.tfstate" # distinct from dev's key
#     region         = "us-east-1"                 # ▢ TODO
#     dynamodb_table = "REPLACE-tf-locks"          # ▢ TODO: lock table
#     encrypt        = true
#   }
# }
#
# --- Google Cloud Storage -----------------------------------------------------
# terraform {
#   backend "gcs" {
#     bucket = "REPLACE-tfstate-bucket"            # ▢ TODO
#     prefix = "envs/prod"                         # distinct from dev's prefix
#   }
# }
#
# --- Terraform Cloud / Enterprise ---------------------------------------------
# terraform {
#   cloud {
#     organization = "REPLACE-org"                 # ▢ TODO
#     workspaces { name = "my-service-prod" }      # ▢ TODO
#   }
# }
