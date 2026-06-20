# outputs.tf — what CALLERS need (ids, endpoints, ARNs). Expose only that.
#
# Outputs are the module's public surface: other modules and the envs read
# these. Keep the set small and stable. Never output a secret in plaintext —
# if you must surface one, mark the output `sensitive = true`.

output "name_prefix" {
  description = "Computed `<name>-<environment>` prefix used for all resources."
  value       = local.name_prefix
}

output "instance_count" {
  description = "Number of instances this module provisioned."
  value       = var.instance_count
}

output "instance_ids" {
  description = "IDs of the provisioned instances (placeholder null_resource ids until you add real infra)."
  value       = null_resource.service[*].id
}

output "tags" {
  description = "The effective tag set applied to resources."
  value       = local.common_tags
}

# ▢ TODO: expose the identifiers/endpoints callers actually consume, e.g.:
# output "service_arn"  { value = aws_ecs_service.this.id }
# output "endpoint_url" { value = "https://${aws_lb.this.dns_name}" }
#
# Example of a sensitive output (rare — prefer not exposing secrets at all):
# output "generated_password" {
#   value     = random_password.db.result
#   sensitive = true
# }
