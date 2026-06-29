# Ch 33 — AWS for AI Engineers

> Companion plan · Part VIII · book file `chapters/33-aws-for-ai-engineers.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the chapter where the capstone gets a real home. The book walks the working subset of
AWS — IAM, VPC, compute, data, messaging, Bedrock — and ends by deploying the platform. The
notebooks make that fluency *runnable without a bill*: every service call runs against
**`moto` / LocalStack** (an in-process / local AWS), so the reader practices IAM least
privilege, S3, DynamoDB, and SQS against the real `boto3` API shapes — and a Bedrock-shaped
model call against a **mock** — without an AWS account. The final notebook is the deploy
*walkthrough as notes*: it maps each capstone component onto concrete services and points at
the Terraform that will stand it up for real in Ch 36.

## Planned notebooks

### 33-01 · `33-01-iam-and-least-privilege.ipynb` — IAM policies and roles, simulated
- **Type:** walkthrough
- **Maps to:** §33.1 (IAM: identity and least privilege)
- **Objective:** write a least-privilege IAM policy and prove it allows exactly what's needed
  and denies the rest — without an AWS account.
- **Prereqs:** Ch 32 (the four primitives; "identity"); basic `boto3` shape from Ch 11/30 helpful.
- **Cell arc:**
  - 🧠 mental model: policies attached to roles/users/groups answer "who can do what to which."
  - Author a tight policy: read *one* S3 bucket, nothing more (JSON document inline).
  - Use `moto`'s IAM + the policy simulator pattern to evaluate allowed vs denied actions.
  - 🔮 *predict* whether `s3:GetObject` on another bucket is allowed, then run the check.
  - ⚠️ pitfall: the `"Action": "s3:*", "Resource": "*"` trap — show the blast radius, then scope it.
  - 🎯 senior lens: roles-not-keys — services assume a role at runtime, so no long-lived keys leak.
- **Datasets/fixtures:** policy JSON authored in-cell; no external data.
- **APIs & cost:** **local-sim only** (`moto`); **no real spend, no AWS account.** `MOCK=1`
  default. There is no live-API path for this notebook — IAM evaluation stays simulated.
- **You'll be able to:** write and sanity-check a least-privilege policy, and explain why roles
  beat long-lived keys.

### 33-02 · `33-02-s3-dynamodb-sqs-on-moto.ipynb` — The data + messaging plane, locally
- **Type:** walkthrough
- **Maps to:** §33.4 (storage and data: S3, DynamoDB), §33.5 (messaging: SQS) — the managed
  equivalents of Ch 30–31
- **Objective:** exercise the capstone's storage and queue plane end-to-end (put/get an object,
  read/write an item, enqueue/consume a task) against simulated AWS.
- **Prereqs:** 33-01; Ch 30 (data layer), Ch 31 (queues/workers).
- **Cell arc:**
  - Stand up S3 + DynamoDB + SQS in-process with `moto` (one setup cell; same `boto3` calls
    you'd use against real AWS).
  - S3: upload a small artifact, list, download, verify bytes round-trip.
  - DynamoDB: model a session item (key + attributes), put then query by key.
  - SQS: send a task message, receive it, delete it — the API↔worker handoff from Ch 31.
  - 🔮 *predict* what `receive_message` returns when the queue is empty (long-poll vs immediate).
  - ⚠️ pitfall: SQS *at-least-once* delivery — design the consumer to be idempotent (Ch 29/31).
  - 🎯 senior lens: `moto` mirrors API *shape*, not every limit/consistency nuance — what still
    needs a real-AWS or LocalStack integration test before you trust it in prod.
  - Note: the same code points at **LocalStack** by setting one `endpoint_url` env var.
- **Datasets/fixtures:** a tiny committed text/JSON artifact in `data/` for the S3 round-trip.
- **APIs & cost:** **local-sim only** (`moto`, optional LocalStack via `endpoint_url`); **no
  real spend.** `MOCK=1` default. ⚠️ Pointing these calls at a real AWS account *would* incur
  charges — left as an explicit, opt-in exercise, not the default.
- **You'll be able to:** drive S3, DynamoDB, and SQS with `boto3` confidently, having run the
  real call shapes for free.

### 33-03 · `33-03-bedrock-call-and-capstone-deploy-notes.ipynb` — Mocked Bedrock + the deploy map
- **Type:** walkthrough  *(carries the chapter's 🔧 Build: "deploy the capstone on AWS" — as a deploy map + notes)*
- **Maps to:** §33.6 (Amazon Bedrock), §33.9 (🔧 Build: deploy the capstone on AWS)
- **Objective:** make a Bedrock-shaped model call behind a mock, then read the capstone's full
  AWS deployment as a component→service map you can hand to the Ch 36 Terraform.
- **Prereqs:** 33-01, 33-02; Ch 11 (model APIs); Ch 13/41 for the Bedrock managed-feature ties.
- **Cell arc:**
  - 🧠 Bedrock as the managed model gateway *inside your AWS perimeter* (one API, data stays in-account).
  - A `bedrock-runtime` `invoke_model` call in the **Anthropic Claude** request/response shape,
    served by `MOCK=1` (canned, realistic completion) — no Bedrock access required.
  - 🔮 *predict* the response envelope (where the text lives) before running the mocked call.
  - Map Bedrock's managed pieces onto patterns built by hand earlier: Knowledge Bases ↔ Ch 13
    RAG, Guardrails ↔ Ch 41 safety + Ch 13 grounding check — a comparison table, not new code.
  - 🎯 senior lens: use Bedrock for *model access* (security/compliance) but keep *orchestration*
    in your own code (the §33.6 senior pattern); decide which layers to outsource deliberately.
  - 🔧 the deploy map: render the §33.9 component→service table (API/workers→Fargate, ALB+
    CloudFront edge, SQS, RDS+pgvector, ElastiCache, S3, Bedrock, CloudWatch, IAM roles, VPC).
  - 📋 the production-readiness checklist from §33.9 (IAM, network, secrets, data, edge,
    resilience, cost, audit, observability) — the bar Ch 36's Terraform must meet.
  - ⚠️ pitfall: a Bedrock model call costs real tokens; the mock is the default — flip to live
    only with credentials and an eye on the per-token bill.
- **Datasets/fixtures:** a tiny committed canned-response JSON for the mocked Bedrock call.
- **APIs & cost:** **mockable.** `MOCK=1` (default) = **no spend, no Bedrock access.** `MOCK=0`
  = ⚠️ **real AWS Bedrock tokens** (opt-in; needs Bedrock model access + credentials); budget a
  couple of short Claude completions. Deploy map/checklist cells are pure-offline.
- **You'll be able to:** call a model through Bedrock's API shape, and read/own the exact
  service map the capstone's IaC will implement.

## Feeds (cross-pillar)
- **Blueprint(s):** — (the LLM-call shape ties to `blueprints/llm/`; observability ties to
  `blueprints/observability-stack/` via CloudWatch/X-Ray).
- **Template(s):** the deploy notes inform [`templates/terraform-module/`](../../templates/terraform-module/)
  (built in Ch 36) and the containerization in
  [`templates/dockerfile-and-compose/`](../../templates/dockerfile-and-compose/) (Ch 35).
- **Capstone:** produces the **AWS deploy notes / service map** consumed by `capstone-project/infra/`;
  the §33.9 architecture is the target that `capstone-project/app/` and `capstone-project/workers/` deploy onto.
  Advances checkpoint `checkpoints/ch33-aws-deploy-map`.

## Dependencies
- Ch 32 (four primitives, FinOps) · Ch 30 (data layer) · Ch 31 (queues/workers) · Ch 11 (model
  APIs). Ch 35 (containers) and Ch 36 (Terraform) consume this chapter's deploy map.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with **no AWS account and no spend**
      (`moto` in-process; LocalStack optional via `endpoint_url`).
- [ ] IAM policy shapes, the S3/DynamoDB/SQS calls, the Bedrock request/response envelope, and
      the §33.9 deploy map + checklist match the book's §33 content.
- [ ] Every real-spend path (live Bedrock, pointing `boto3` at real AWS) is clearly flagged ⚠️
      and opt-in; secrets/credentials read from env only.
- [ ] Each notebook ends with recap + exercises and links onward to the Ch 36 Terraform and
      `capstone-project/infra/`.
