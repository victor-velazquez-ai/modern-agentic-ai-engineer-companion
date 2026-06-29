# main.tf — the platform's AWS architecture (Appendix C: VPC, ECS/Fargate, RDS,
# ElastiCache, S3).
#
# This skeleton uses `null_resource` placeholders so the whole module `init`s,
# `validate`s, and `plan`s with NO cloud provider and NO spend — that is the
# capstone default and what Ch 36's plan/apply walkthrough runs against. Each
# placeholder records the resolved inputs so `terraform plan` shows meaningful,
# inspectable output. The real `aws_*` resources are alongside, commented, ready
# to switch on once you enable the aws provider in versions.tf (Ch 33).

locals {
  name_prefix = "${var.name}-${var.environment}"

  artifacts_bucket = (
    var.artifacts_bucket_name != ""
    ? var.artifacts_bucket_name
    : "${local.name_prefix}-artifacts"
  )

  common_tags = merge(
    {
      Name        = local.name_prefix
      Environment = var.environment
      ManagedBy   = "terraform"
      Module      = "platform"
      Application = "agentic-platform"
    },
    var.tags,
  )
}

# --- Networking (VPC + subnets) ---------------------------------------------
# Placeholder. Real: one aws_vpc + public/private aws_subnet per AZ, an
# internet gateway, NAT, and route tables.
resource "null_resource" "vpc" {
  triggers = {
    name     = "${local.name_prefix}-vpc"
    cidr     = var.vpc_cidr
    az_count = var.az_count
    region   = var.aws_region
  }
}

# resource "aws_vpc" "this" {
#   cidr_block           = var.vpc_cidr
#   enable_dns_support   = true
#   enable_dns_hostnames = true
#   tags                 = merge(local.common_tags, { Name = "${local.name_prefix}-vpc" })
# }

# --- Compute (ECS cluster + Fargate services for api & worker) --------------
# Placeholder. Real: aws_ecs_cluster + two aws_ecs_service (api, worker) using
# one shared task image, behind an ALB for the api.
resource "null_resource" "ecs" {
  triggers = {
    cluster              = "${local.name_prefix}-cluster"
    image                = var.service_image
    api_desired_count    = var.api_desired_count
    worker_desired_count = var.worker_desired_count
    task_cpu             = var.task_cpu
    task_memory          = var.task_memory
  }
}

# resource "aws_ecs_cluster" "this" {
#   name = "${local.name_prefix}-cluster"
#   tags = local.common_tags
# }
# resource "aws_ecs_service" "api" {
#   name            = "${local.name_prefix}-api"
#   cluster         = aws_ecs_cluster.this.id
#   desired_count   = var.api_desired_count
#   launch_type     = "FARGATE"
#   task_definition = aws_ecs_task_definition.api.arn
#   tags            = local.common_tags
# }

# --- Data: RDS Postgres (pgvector) ------------------------------------------
# Placeholder. Real: aws_db_subnet_group + aws_db_instance (engine = postgres,
# with the pgvector extension created via a migration).
resource "null_resource" "rds" {
  triggers = {
    identifier        = "${local.name_prefix}-pg"
    instance_class    = var.db_instance_class
    allocated_storage = var.db_allocated_storage
    # Never echo the password into triggers/outputs — only whether it's set.
    has_db_password = var.db_password != "" ? "yes" : "no"
  }
}

# resource "aws_db_instance" "postgres" {
#   identifier        = "${local.name_prefix}-pg"
#   engine            = "postgres"
#   instance_class    = var.db_instance_class
#   allocated_storage = var.db_allocated_storage
#   username          = "agent"
#   password          = var.db_password        # from TF_VAR_db_password
#   skip_final_snapshot = var.environment != "prod"
#   tags              = local.common_tags
# }

# --- Data: ElastiCache Redis (Celery broker + cache) ------------------------
# Placeholder. Real: aws_elasticache_subnet_group + aws_elasticache_cluster.
resource "null_resource" "redis" {
  triggers = {
    cluster_id = "${local.name_prefix}-redis"
    node_type  = var.redis_node_type
  }
}

# resource "aws_elasticache_cluster" "redis" {
#   cluster_id      = "${local.name_prefix}-redis"
#   engine          = "redis"
#   node_type       = var.redis_node_type
#   num_cache_nodes = 1
#   tags            = local.common_tags
# }

# --- Object storage: S3 (artifacts / document uploads) ----------------------
# Placeholder. Real: aws_s3_bucket + public-access-block + versioning + SSE.
resource "null_resource" "s3" {
  triggers = {
    bucket = local.artifacts_bucket
  }
}

# resource "aws_s3_bucket" "artifacts" {
#   bucket = local.artifacts_bucket
#   tags   = local.common_tags
# }
# resource "aws_s3_bucket_public_access_block" "artifacts" {
#   bucket                  = aws_s3_bucket.artifacts.id
#   block_public_acls       = true
#   block_public_policy     = true
#   ignore_public_acls      = true
#   restrict_public_buckets = true
# }
