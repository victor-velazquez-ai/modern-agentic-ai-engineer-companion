# Template — Terraform Module
> Realizes book Ch 36 · Status: 📋 planned (Phase 1)

## What it scaffolds
A reusable Terraform **module** skeleton — `variables.tf` / `main.tf` / `outputs.tf` with the
standard input/output contract — plus a `envs/dev|prod` layout that consumes the module with
per-environment values, so infra is written once and parameterized, not copy-pasted.

## When to copy it
You're writing infrastructure you'll stand up in more than one environment (dev and prod, or
per-service) and want a clean, reusable module instead of click-ops or a wall of duplicated
HCL. Copy `infra/` into your repo and `terraform plan` against `envs/dev`.

## Planned file tree
```text
terraform-module/
├── README.md                  # inputs/outputs, how envs consume it; "copy me"
├── modules/
│   └── service/               # ▢ rename to your resource (e.g. ecs-service, rds)
│       ├── main.tf            # the resources — # TODO: declare your infra
│       ├── variables.tf       # typed inputs with descriptions + sensible defaults
│       ├── outputs.tf         # what callers need (ids, endpoints, ARNs)
│       └── versions.tf        # required_providers + Terraform version pin
└── envs/
    ├── dev/
    │   ├── main.tf            # calls ../../modules/service with dev values
    │   ├── terraform.tfvars   # ▢ non-secret dev values (secrets via env/TF_VAR, not here)
    │   └── backend.tf         # ▢ remote state backend (commented stub)
    └── prod/
        ├── main.tf            # same module, prod values
        ├── terraform.tfvars   # ▢ non-secret prod values
        └── backend.tf
```

## Defaults baked in
- **Module / env split:** reusable logic in `modules/`, environment differences isolated to
  `envs/*/` — change behavior once, vary only values per env.
- **Typed I/O contract:** every variable has a `type` + `description` (+ default where safe);
  `outputs.tf` exposes only what callers need; `versions.tf` pins Terraform + provider.
- **Secrets never in HCL or tfvars:** sensitive inputs are `sensitive = true` and supplied via
  `TF_VAR_*` / a secrets backend; `terraform.tfvars` holds non-secret config only.
- **Remote-state ready:** a commented `backend.tf` stub so teams enable shared, locked state
  (and never commit local state).
- **Plan-first / local-friendly:** designed to `validate`/`plan` cleanly; the book's notebook
  runs it locally (no live cloud spend required to learn it).
- **Provider-pinned:** versions pinned for reproducible `plan`s.

## Maps to the book
- **Ch 36 — Infrastructure as Code:** the reusable-module + dev/prod-env pattern, Terraform
  plan/apply (🔧 Build, run locally).
- **Notebook:** the [`learn/part-08-…/36-infrastructure-as-code/`](../../learn/) walkthrough
  does `plan`/`apply` against this. **Capstone:** mirrors `infra/modules/` and
  `infra/envs/dev|prod/` in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ)
  (the Terraform that stands up VPC/ECS/RDS for the platform). **Template:** pairs with
  [`../github-actions-ci/`](../github-actions-ci/PLAN.md) for `plan` on PR.

## Phase-2 definition of done
- [ ] `terraform init && terraform validate` passes in `envs/dev` and `envs/prod`.
- [ ] `terraform plan` runs against the module (with example/`null`-style resources or a local provider) with no errors.
- [ ] Variables are typed + described; outputs defined; provider/TF versions pinned.
- [ ] No secrets in any `.tf`/`.tfvars`; sensitive inputs marked `sensitive` and sourced from env; state not committed.
