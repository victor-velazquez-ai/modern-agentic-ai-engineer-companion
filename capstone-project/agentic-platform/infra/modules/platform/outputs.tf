# outputs.tf — what CALLERS (the envs) read back. Expose only that.
#
# Outputs are the module's public surface. Keep the set small and stable, and
# never output a secret in plaintext (mark `sensitive = true` if you must).

output "name_prefix" {
  description = "Computed `<name>-<environment>` prefix used for all resources."
  value       = local.name_prefix
}

output "vpc_id" {
  description = "ID of the platform VPC (placeholder null_resource id until aws is enabled)."
  value       = null_resource.vpc.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster the api + worker run in."
  value       = null_resource.ecs.triggers.cluster
}

output "artifacts_bucket" {
  description = "Name of the S3 bucket for artifacts / document uploads."
  value       = local.artifacts_bucket
}

output "tags" {
  description = "The effective tag set applied to resources."
  value       = local.common_tags
}

# Once the real aws provider is enabled, surface the identifiers callers consume:
# output "alb_dns_name" { value = aws_lb.api.dns_name }
# output "db_endpoint"  { value = aws_db_instance.postgres.address }
# output "redis_endpoint" { value = aws_elasticache_cluster.redis.cache_nodes[0].address }
