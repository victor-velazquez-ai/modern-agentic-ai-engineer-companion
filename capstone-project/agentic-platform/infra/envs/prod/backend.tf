# envs/prod/backend.tf — REMOTE STATE backend (commented stub).
#
# Production state MUST live in a shared, locked, encrypted remote backend —
# never a local file. Keep prod on a SEPARATE state path/workspace from dev so
# they can never clobber each other. State can contain secrets; the repo
# .gitignore excludes *.tfstate*.
#
# Pick ONE backend, uncomment it, fill the placeholders, then run
# `terraform init -migrate-state`.

# --- AWS S3 + DynamoDB lock --------------------------------------------------
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE-tfstate-bucket"
#     key            = "envs/prod/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "REPLACE-tf-locks"
#     encrypt        = true
#   }
# }
