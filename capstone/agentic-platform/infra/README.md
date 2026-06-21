# `infra/` — Terraform: the platform's AWS target (Ch 33, 36)

Infrastructure as code for the `agentic-platform`. One reusable **module**
(`modules/platform/`) describes the architecture; two **environments**
(`envs/dev/`, `envs/prod/`) compose it with their own values. Behavior lives in
the module; only *values* differ between dev and prod.

> Built in **Ch 36 — Infrastructure as Code** (§36.4 plan/apply), targeting the
> AWS architecture stood up in **Ch 33**. Standalone pattern:
> [`templates/terraform-module/`](../../../templates/terraform-module/).

```text
infra/
├── modules/
│   └── platform/            # the architecture, written once
│       ├── main.tf          #   VPC · ECS/Fargate · RDS · ElastiCache · S3
│       ├── variables.tf     #   typed inputs (secrets are sensitive = true)
│       ├── outputs.tf       #   ids/endpoints callers read back
│       └── versions.tf      #   Terraform + provider version pins
└── envs/
    ├── dev/                 # calls ../../modules/platform with dev values
    │   ├── main.tf
    │   ├── terraform.tfvars #   non-secret dev values (secrets via TF_VAR_*)
    │   └── backend.tf       #   remote-state backend (commented stub)
    └── prod/                # same module, prod values (HA sizing)
        ├── main.tf
        ├── terraform.tfvars
        └── backend.tf
```

## What it provisions (Appendix C)

| Resource | Purpose |
|---|---|
| **VPC** + subnets across AZs | Network isolation, HA |
| **ECS / Fargate** (api + worker) | Runs the one shared container image (`../Dockerfile`) |
| **RDS Postgres** (pgvector) | Relational store + embeddings |
| **ElastiCache Redis** | Celery broker, result backend, app cache |
| **S3** | Document uploads / build artifacts |

## Plans offline — no cloud, no spend

The module ships with `null_resource` placeholders and the `hashicorp/null`
provider, so it **`init`s, `validate`s, and `plan`s with no AWS account**. Each
placeholder records its resolved inputs, so `terraform plan` shows meaningful
output you can inspect — exactly the Ch 36 walkthrough. The real `aws_*` resource
blocks sit alongside each placeholder, commented, ready to switch on.

```bash
cd envs/dev          # each env is its own Terraform root
terraform init
terraform validate
terraform plan
```

Repeat in `envs/prod`. You `init`/`plan`/`apply` **inside** an env, not at the
`infra/` root.

## Going live (Ch 33)

1. Uncomment the `aws` provider in `modules/platform/versions.tf` and each env's
   `required_providers`; add a `provider "aws" { region = ... }` block in the env
   `main.tf` (commented stub provided).
2. Replace each `null_resource.*` in `modules/platform/main.tf` with the
   commented `aws_*` block above it; delete the `null` provider once unused.
3. Wire the new outputs (ALB DNS, DB endpoint, Redis endpoint) so the ECS task
   definition can read its `DATABASE_URL` / `REDIS_URL` (see `../.env.example`).

## Secrets policy

- **Never** put a secret in any `.tf` or `.tfvars` file — those are committed.
- Sensitive inputs (`db_password`) are declared `sensitive = true` and supplied
  through the environment:

  ```bash
  export TF_VAR_db_password="..."        # bash / zsh
  ```
  ```powershell
  $env:TF_VAR_db_password = "..."        # PowerShell
  ```
  For teams, source them from AWS Secrets Manager / SSM (Ch 33 deploy-time
  secrets), not a shell export.
- **State is sensitive too** — `terraform.tfstate` is git-ignored; keep dev and
  prod on separate remote-state paths (see `backend.tf`).

Pairs with `../.github/workflows/` to run `terraform plan` on every PR.
