# versions.tf — pin Terraform + providers so every `plan` is reproducible.
#
# A module should declare the versions it is *known to work with*. Callers
# (the envs) inherit these constraints. Pinning here, not in each env, keeps
# the contract in one place.

terraform {
  # Pin the Terraform CLI version. `~> 1.6` means >= 1.6.0 and < 2.0.0.
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    # ▢ TODO: replace/extend with the providers your resources actually use
    #         (e.g. aws, google, azurerm, kubernetes). The `null` provider is
    #         baked in so this module `validate`s and `plan`s with NO cloud
    #         account and NO spend — delete it once you add a real provider.
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }

    # Example real provider (commented until you need it):
    # aws = {
    #   source  = "hashicorp/aws"
    #   version = "~> 5.0"
    # }
  }
}
