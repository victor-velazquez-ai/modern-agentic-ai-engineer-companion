# envs/dev/backend.tf — REMOTE STATE backend (commented stub).
#
# By default Terraform keeps state in a local `terraform.tfstate` file. That is
# fine to *learn* with, but a team should use a shared, locked, remote backend
# so state is not lost and two people can't apply at once. State can contain
# secrets, so it must NEVER be committed (see the repo .gitignore for *.tfstate).
#
# ▢ TODO: pick ONE backend, uncomment it, fill the placeholders, then run
#         `terraform init -migrate-state` to move local state into it.
#
# --- AWS S3 + DynamoDB lock ---------------------------------------------------
# terraform {
#   backend "s3" {
#     bucket         = "REPLACE-tfstate-bucket"   # ▢ TODO: existing, versioned bucket
#     key            = "envs/dev/terraform.tfstate"
#     region         = "us-east-1"                # ▢ TODO
#     dynamodb_table = "REPLACE-tf-locks"         # ▢ TODO: lock table
#     encrypt        = true
#   }
# }
#
# --- Google Cloud Storage -----------------------------------------------------
# terraform {
#   backend "gcs" {
#     bucket = "REPLACE-tfstate-bucket"           # ▢ TODO
#     prefix = "envs/dev"
#   }
# }
#
# --- Terraform Cloud / Enterprise ---------------------------------------------
# terraform {
#   cloud {
#     organization = "REPLACE-org"                # ▢ TODO
#     workspaces { name = "my-service-dev" }      # ▢ TODO
#   }
# }
