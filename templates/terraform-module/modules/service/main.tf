# main.tf — the resources this module manages.
#
# This skeleton uses the `null_resource` placeholder so the module `init`s,
# `validate`s, and `plan`s with NO cloud provider and NO spend. Replace the
# placeholder with your real infrastructure (ECS service, RDS instance, GKE
# deployment, ...) and delete the `null` provider from versions.tf.
#
# ▢ TODO: declare your infra here.

locals {
  # One place to assemble naming + tags so every resource is consistent.
  name_prefix = "${var.name}-${var.environment}"

  common_tags = merge(
    {
      Name        = local.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "service"
    },
    var.tags,
  )
}

# --- Placeholder resource (delete once you add real infra) -------------------
# `null_resource` lets the whole template plan cleanly with no provider/cloud.
# `triggers` simply records the resolved inputs so `terraform plan` shows
# meaningful, non-empty output you can inspect.
resource "null_resource" "service" {
  count = var.instance_count

  triggers = {
    name        = local.name_prefix
    environment = var.environment
    index       = count.index
    # `api_key` is sensitive — DO NOT echo it into triggers or any output.
    has_api_key = var.api_key != "" ? "yes" : "no"
    tags        = jsonencode(local.common_tags)
  }
}

# --- Example real resource (commented; needs the aws provider in versions.tf)-
# resource "aws_ecs_service" "this" {
#   name            = local.name_prefix
#   desired_count   = var.instance_count
#   task_definition = var.task_definition_arn   # add the input in variables.tf
#   tags            = local.common_tags
# }
