# Part VIII — Cloud & Infrastructure

> Companion to **Modern Agentic AI Engineer**, Part VIII · book chapters 32–36
> Status: 📋 planned (Phase 1)

## Companion emphasis

This is where the capstone gets a **home in the cloud** — defined as code, shipped by a
pipeline, ready to scale. The arc: install the cloud mental model and FinOps discipline
(Ch 32) → go deep on the working subset of AWS and map the capstone onto real services
(Ch 33) → see other clouds as *translation, not relearning* (Ch 34) → containerize the
service (Ch 35) → capture the whole architecture as Terraform behind a gated CI/CD pipeline
(Ch 36). Two through-lines run the whole part: **the four primitives** (compute · storage ·
network · identity) make any cloud legible, and **operational leverage vs operational cost**
governs every "should we reach for this?" decision (Fargate vs Kubernetes, one cloud vs
multi-cloud, console vs IaC).

## ⚠️ These notebooks default to local simulation — no cloud bill

Cloud is the one part that's genuinely hard to run cheaply, so **every notebook here runs free
and offline by default** (`MOCK=1`). We lean on local simulation throughout:

- **AWS → `moto` / LocalStack.** IAM least-privilege, S3, DynamoDB, and SQS run against an
  in-process / local AWS using the *real* `boto3` call shapes — **no AWS account required.**
- **Bedrock → mocked.** Model calls use the real Anthropic-Claude-on-Bedrock request/response
  shape behind a canned response; **no Bedrock access or tokens** unless you opt in.
- **Terraform → `init` / `validate` / `plan` only.** You see the reviewable diff with **no
  `apply`, no provisioning, no spend.**
- **Kubernetes → read-and-simulate.** Manifests are parsed and a desired-state reconcile/HPA
  loop is simulated **without a cluster.**
- **Docker → local only.** The one real local dependency; still **no cloud, no spend** (cells
  degrade to printed commands if Docker is absent).

Anything that would incur **real cloud spend** (a live Bedrock call, pointing `boto3` at a real
account, `terraform apply`) is **clearly flagged ⚠️ and strictly opt-in** — never the default,
never run in CI. Secrets and credentials come from the environment only.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 32 | Cloud Foundations | Concept lab — classify any service into the four primitives, then run an offline FinOps cost toy (on-demand/spot/reserved, the forgotten-resource trap). No account, no spend. | [`32-cloud-foundations/PLAN.md`](32-cloud-foundations/PLAN.md) |
| 33 | AWS for AI Engineers | Walkthroughs against `moto`/LocalStack — IAM least privilege, S3/DynamoDB/SQS, a mocked Bedrock call; ends with the 🔧 capstone **deploy map** (component → service) + readiness checklist. | [`33-aws-for-ai-engineers/PLAN.md`](33-aws-for-ai-engineers/PLAN.md) |
| 34 | Azure & GCP for AI | Concept lab — translate an AWS design to Azure/GCP by primitive, then prove "portability without multi-cloud" by swapping a provider behind one interface. Offline fakes, no spend. | [`34-azure-and-gcp/PLAN.md`](34-azure-and-gcp/PLAN.md) |
| 35 | Containers & Kubernetes | 🔧 Walkthrough — Dockerize the FastAPI service (multi-stage, non-root) + Compose, feeding `templates/dockerfile-and-compose/`; plus a concept lab that reads K8s manifests and simulates HPA scaling without a cluster. | [`35-containers-and-kubernetes/PLAN.md`](35-containers-and-kubernetes/PLAN.md) |
| 36 | Infrastructure as Code & Platform Engineering | 🔧 Walkthrough — author a Terraform module and run `plan` locally (no `apply`), feeding `templates/terraform-module/` + `capstone/infra/`; plus a concept lab modeling CI/CD as a quality gate with an **eval gate**. | [`36-infrastructure-as-code/PLAN.md`](36-infrastructure-as-code/PLAN.md) |

## Run order

Read in chapter order — the part builds on itself. **32** sets the mental model and FinOps
lens everything else uses. **33** is the heart: the `moto`/LocalStack walkthroughs plus the
capstone's AWS deploy map. **34** is a short translation/portability detour. **35** produces
the container image, and **36** wraps that image in Terraform behind a gated pipeline — the
closing milestone (`checkpoints/ch36-infra-as-code`) that gives the capstone a real,
reproducible home. The build artifacts of this part — the deploy map (Ch 33),
`templates/dockerfile-and-compose/` (Ch 35), and `templates/terraform-module/` +
`capstone/infra/` (Ch 36) — are what Part X (Production LLMOps) operates on.
