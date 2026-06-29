# Ch 36 — Infrastructure as Code & Platform Engineering

> Companion plan · Part VIII · book file `chapters/36-infrastructure-as-code.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is where the capstone's AWS architecture (Ch 33) becomes a *reviewable, reproducible*
artifact. The **walkthrough** has the reader author a real Terraform module for a slice of the
platform and run `init → validate → plan` **locally** — `plan` shows the diff with **no
`apply`, no cloud account, no spend**, so the reader sees IaC's payoff (reviewable diffs,
parameterized environments, secrets-by-reference) for free. A second short **concept lab**
treats CI/CD as the quality gate — including the AI-specific *eval gate* — by simulating the
pipeline's pass/fail logic offline. The Terraform here is the §36.4 🔧 Build; it becomes
`templates/terraform-module/` and `capstone-project/infra/`.

## Planned notebooks

### 36-01 · `36-01-terraform-plan-locally.ipynb` — 🔧 Build: reproducible infra, planned offline
- **Type:** walkthrough  *(this is the chapter's 🔧 Build — §36.4 reproducible infrastructure)*
- **Maps to:** §36.1 (IaC: Terraform & CDK), §36.2 (environments, config, secrets),
  §36.4 (🔧 Build: reproducible infrastructure for the capstone)
- **Objective:** write a small Terraform module for a capstone slice and run `validate`/`plan`
  locally to see the exact change set — without applying anything or touching a real account.
- **Prereqs:** Ch 33 (the AWS service map being codified); Ch 28 (12-factor config); Terraform
  CLI installed locally (no AWS credentials needed for `validate`; `plan` uses a fake/no-op
  provider config or `terraform plan` against the module in isolation).
- **Cell arc:**
  - 🧠 mental model: declarative desired-state for your whole account — same idea as K8s (Ch 35),
    applied to cloud infra; the tool reconciles reality to the files.
  - Author HCL for a capstone slice — the §36.1 `aws_ecs_service` (Fargate, `desired_count = 3`
    across AZs) plus its cluster/task-definition and an S3 bucket — parameterized by variables.
  - `terraform init` + `validate`: catch errors statically; 🔮 *predict* a validation failure
    from a deliberately bad type, then fix it.
  - `terraform plan`: read the proposed diff (create/change/destroy) — the reviewable artifact;
    🔮 *predict* the resource count before reading the plan.
  - Environments: show dev/staging/prod as the *same* code with different `tfvars` (§36.2) — no
    divergent copies.
  - ⚠️ pitfall: secrets in IaC/state — reference Secrets Manager / SSM by ARN so the code says
    *where*, never the secret value (§36.2); note state files can hold sensitive data.
  - ⚠️ pitfall: **`terraform apply` against real AWS provisions billable resources** — this
    notebook stops at `plan`; `apply` is explicitly out of scope and opt-in only.
  - 🎯 senior lens: IaC makes infra reviewable / reproducible / auditable / recoverable — the
    §36.1 payoff; manual console changes are silent tech debt.
  - Ends pointing at the production module: [`templates/terraform-module/`](../../templates/terraform-module/)
    and the capstone's `capstone-project/infra/`.
- **Datasets/fixtures:** the `.tf` and `.tfvars` authored in the chapter folder; no external data.
- **APIs & cost:** **local-sim only.** `init`/`validate`/`plan` run **offline with no AWS
  account and no spend.** ⚠️ `terraform apply` (real provisioning) is **out of scope / opt-in**
  and clearly flagged; never run by default or in CI.
- **You'll be able to:** author a Terraform module, read a `plan` diff, parameterize
  environments, and keep secrets out of code — all without provisioning or paying.

### 36-02 · `36-02-cicd-as-a-quality-gate.ipynb` — The pipeline, including the eval gate
- **Type:** concept-lab
- **Maps to:** §36.3 (CI/CD for applications and infrastructure), §36.5 (🎯 platform engineering)
- **Objective:** model a CI/CD pipeline as a quality gate — lint, types, tests, **and evals** —
  that blocks a merge on regression, and reason about progressive delivery, all offline.
- **Prereqs:** 36-01; Ch 7 (testing/CI); Part VI (evals) for the eval-gate concept.
- **Cell arc:**
  - 🧠 mental model: CI on every change (lint/type/test/**eval**); CD ships only what passes
    (build image → apply IaC → staging → canary → prod) — the §36.3 pipeline.
  - A tiny offline pipeline simulator: a list of stages with pass/fail; run it on a "good" change.
  - 🔧 the **eval gate** (§36.3 tip / Part VI): feed a small eval score; 🔮 *predict* whether a
    prompt change that drops the score below threshold blocks the merge, then run it and see.
  - Progressive delivery: simulate a canary watching a metric and auto-rolling-back on a dip
    (Ch 28) — a small state machine, no real deploy.
  - ⚠️ pitfall: a pipeline that automates but doesn't *gate* — a quality regression sails through;
    the fix is blocking on tests/types/evals together.
  - 🎯 senior lens (§36.5): **platform engineering** — codifying paved-road defaults (security,
    observability, cost, rollouts) so the whole org ships safely; leverage shifts from deploying
    your service to enabling everyone's.
- **Datasets/fixtures:** a tiny committed `data/eval-scores.json` (baseline vs candidate) for
  the gate demo; pipeline stages defined in-cell.
- **APIs & cost:** none — fully offline. **No CI runner, no cloud, no spend**; the pipeline and
  canary are simulated.
- **You'll be able to:** design a CI/CD pipeline that gates on tests *and* evals, explain
  canary rollback, and articulate what platform engineering buys an organization.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the eval gate ties to `blueprints/eval-harness/` from Part VI; no new one).
- **Template(s):** **produces** [`templates/terraform-module/`](../../templates/terraform-module/)
  (the §36.4 module hardened into a copy-into-your-job scaffold). The pipeline concept reinforces
  the CI template from Ch 7.
- **Capstone:** **produces** `capstone-project/infra/` — the full Terraform for the Ch 33 architecture
  (VPC/subnets, ECS cluster + Fargate services, RDS+pgvector, ElastiCache, S3, SQS, IAM roles,
  CloudWatch alarms), deployed by the pipeline. Advances checkpoint `checkpoints/ch36-infra-as-code`
  — the closing milestone of Part VIII.

## Dependencies
- Ch 33 (AWS architecture to codify) · Ch 35 (the container image the infra deploys) · Ch 28
  (12-factor config, progressive delivery) · Ch 7 + Part VI (CI and the eval gate).

## Phase-2 definition of done
- [ ] 36-01 runs `init`/`validate`/`plan` locally with **no AWS account and no spend**; `apply`
      is never invoked and is flagged opt-in. 36-02 runs fully offline (simulated pipeline).
- [ ] The HCL shape, the environments/secrets discipline, the CI/CD stages, and the eval gate
      match the book's §36 content and the §36.4 Build.
- [ ] 36-01 ends pointing at `templates/terraform-module/` and `capstone-project/infra/`; no secrets in
      `.tf`/state/committed outputs — referenced by ARN only.
- [ ] Each notebook ends with recap + exercises and links onward (template, `capstone-project/infra/`,
      the Part VI eval harness).
