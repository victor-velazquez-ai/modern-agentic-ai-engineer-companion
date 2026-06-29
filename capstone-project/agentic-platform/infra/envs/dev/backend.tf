# envs/dev/backend.tf — REMOTE STATE backend (commented stub).
#
# By default Terraform keeps state in a local `terraform.tfstate` file — fine to
# learn with. A team should use a shared, locked, remote backend so state is not
# lost and two applies can't collide. State can contain secrets, so it must
# NEVER be committed (the repo .gitignore excludes *.tfstate*).
#
# Pick ONE backend, uncomment it, fill the placeholders, then run
# `terraform init -migrate-state` to move local state into it.

# --- AWS S3 + DynamoDB lock --------------------------------------------------
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE-tfstate-bucket"   # existing, versioned bucket
#     key            = "envs/dev/terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "REPLACE-tf-locks"         # lock table
#     encrypt        = true
#   }
# }
