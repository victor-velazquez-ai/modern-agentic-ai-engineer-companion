# versions.tf — pin Terraform + providers so every `plan` is reproducible.
#
# A module declares the versions it is known to work with; the envs inherit
# these constraints. Pinning here (not per-env) keeps the contract in one place.

terraform {
  # `~> 1.6` means >= 1.6.0 and < 2.0.0.
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    # The `null` provider is baked in so this module `init`s, `validate`s, and
    # `plan`s with NO cloud account and NO spend — the capstone build runs
    # offline by default (Ch 36 demonstrates plan/apply with this skeleton).
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }

    # Uncomment to provision the real AWS architecture (Ch 33). Then replace the
    # null_resource placeholders in main.tf with the commented aws_* blocks.
    # aws = {
    #   source  = "hashicorp/aws"
    #   version = "~> 5.0"
    # }
  }
}
