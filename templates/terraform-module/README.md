# Template — Terraform Module (reusable module + dev/prod envs)

> **Copy me.** Drop this folder into your repo (commonly as `infra/`), fill the
> `TODO` / `▢` markers, and you have a reusable Terraform **module** consumed by
> separate **dev** and **prod** environments. Delete this notice once adapted.

Write your infrastructure **once** as a module, then parameterize it per
environment — instead of click-ops or a wall of copy-pasted HCL. The behavior
lives in `modules/`; only the *values* differ between `envs/dev` and
`envs/prod`.

```text
terraform-module/
├── README.md                  # you are here
├── modules/
│   └── service/               # ▢ rename to your resource (ecs-service, rds, ...)
│       ├── main.tf            # the resources — # TODO: declare your infra
│       ├── variables.tf       # typed inputs with descriptions + safe defaults
│       ├── outputs.tf         # what callers need (ids, endpoints, ARNs)
│       └── versions.tf        # required_providers + Terraform version pin
└── envs/
    ├── dev/
    │   ├── main.tf            # calls ../../modules/service with dev values
    │   ├── terraform.tfvars   # ▢ non-secret dev values (secrets via TF_VAR_*)
    │   └── backend.tf         # ▢ remote state backend (commented stub)
    └── prod/
        ├── main.tf            # same module, prod values
        ├── terraform.tfvars   # ▢ non-secret prod values
        └── backend.tf
```

The skeleton uses the `hashicorp/null` provider and a `null_resource`
placeholder so it **`init`s, `validate`s, and `plan`s with no cloud account and
no spend**. Swap in a real provider (`aws`, `google`, `azurerm`, ...) and real
resources when you're ready.

---

## Copy and use

```bash
# 1. Copy this template into your repo (rename to infra/ if you like).
cp -r templates/terraform-module ./infra
cd ./infra

# 2. Find every placeholder and resolve it.
grep -rn "TODO\|▢" .

# 3. Plan the dev environment (no cloud needed with the placeholder provider).
cd envs/dev
terraform init
terraform validate
terraform plan
```

Repeat step 3 in `envs/prod`. Each environment is an independent Terraform
root: you `init`/`plan`/`apply` **inside** `envs/dev` or `envs/prod`, not at the
template root.

---

## What goes where

| You want to change... | Edit... |
|-----------------------|---------|
| **What** the infra is (add a resource, change wiring) | `modules/service/main.tf` (+ `variables.tf`, `outputs.tf`) |
| A **new input** the module accepts | `modules/service/variables.tf` (typed + described) |
| What callers can **read back** | `modules/service/outputs.tf` |
| Terraform / provider **versions** | `modules/service/versions.tf` |
| **dev** sizing/naming values | `envs/dev/terraform.tfvars` |
| **prod** sizing/naming values | `envs/prod/terraform.tfvars` |
| Where **state** is stored | `envs/<env>/backend.tf` |

**Rule of thumb:** behavior in `modules/`, values in `envs/*`. If you find
yourself copy-pasting resource blocks between dev and prod, that logic belongs
in the module.

---

## Customizing for real infrastructure

1. **Rename the module.** `modules/service/` → e.g. `modules/ecs-service/`, and
   update each env's `module "service" { source = "../../modules/..." }`.
2. **Add a real provider.** In `modules/service/versions.tf`, replace the `null`
   provider with yours (e.g. `aws ~> 5.0`); do the same in each env's
   `required_providers`, and add a `provider "aws" { region = ... }` block in
   the env `main.tf` (there's a commented stub).
3. **Declare resources.** Replace `null_resource.service` in
   `modules/service/main.tf` with your real resources; delete the `null`
   provider once nothing uses it.
4. **Define the I/O contract.** Add typed, described inputs to `variables.tf`
   (mark secrets `sensitive = true`) and expose only what callers need in
   `outputs.tf`.
5. **Wire the envs.** Pass the new inputs through each env's `module "service"`
   block and set non-secret values in `terraform.tfvars`.

---

## Secrets policy

- **Never** put a secret in any `.tf` or `.tfvars` file — those are committed.
- Sensitive inputs are declared `sensitive = true` and supplied through the
  environment as `TF_VAR_<name>`:

  ```bash
  export TF_VAR_api_key="..."     # bash / zsh
  ```
  ```powershell
  $env:TF_VAR_api_key = "..."     # PowerShell
  ```
  For teams, source them from a real secrets backend (AWS Secrets Manager,
  Vault, SSM) rather than a shell export.
- `terraform.tfvars` holds **non-secret** config only (names, counts, tags).
- **State is sensitive too.** `terraform.tfstate` can contain secret values —
  it must be git-ignored (the repo `.gitignore` already excludes `*.tfstate*`)
  and, for teams, kept in a remote backend (see below).

---

## Remote state (`backend.tf`)

Each env ships a **commented** `backend.tf` stub. Local state is fine to learn
with; a team should enable a shared, locked, encrypted remote backend so state
is never lost and two applies can't collide.

1. Pick one backend (S3+DynamoDB, GCS, or Terraform Cloud) in
   `envs/<env>/backend.tf` and uncomment it.
2. Fill the `REPLACE-*` placeholders. Keep **dev and prod on separate state
   paths/workspaces** so they can never clobber each other.
3. Run `terraform init -migrate-state` to move local state into the backend.

---

## Realizes (book chapters)

- **Ch 36 — Infrastructure as Code:** the reusable-module + dev/prod-env
  pattern, and Terraform `plan`/`apply` run locally (the chapter that produces
  this template).
- **Notebook:** `learn/part-08-.../36-infrastructure-as-code/` does `plan`/`apply`
  against this module.
- **Capstone:** `chapters/92-appendix-capstone.typ` mirrors this `modules/` +
  `envs/dev|prod/` layout to stand up the platform's VPC/ECS/RDS.
- **Pairs with** the [`github-actions-ci`](../github-actions-ci/README.md)
  template to run `terraform plan` on every PR.
