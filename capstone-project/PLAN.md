# Capstone — directory-by-directory build plan

> Companion plan · the `agentic-platform` reference · book Appendix C (`chapters/92-appendix-capstone.typ`)
> Status: 📋 planned (Phase 1)

This is the build plan for the capstone's source tree: for **each top-level directory**, its
purpose, the chapter(s) and 🔧 Build section that build it in the book, and the `learn/`
walkthrough + pattern `blueprints/` it corresponds to. Appendix C's tree is the spine;
directories the chapters add on top are marked **(extends Appendix C)** and justified inline.

**How to read this (pedagogy):** these rows are *not* a checklist of folders to copy. They
are the map from each Build section to the directory you'll produce yourself, plus the
isolated walkthrough and the "how a senior structures it" blueprint to learn the pattern from.
Build the directory from the chapter; consult the blueprint for the pattern; diff against the
[checkpoint](checkpoints/PLAN.md) when stuck. See [`README.md`](README.md) for the rule.

---

## The directory map at a glance

| Directory | Purpose | Built in (chapter · 🔧 Build) | `learn/` walkthrough | Pattern `blueprints/` |
|---|---|---|---|---|
| [`app/`](#app--fastapi-backend) | FastAPI backend: routes, settings, domain, db, services | Ch 25 (§25 Build), 26, 28 | 25 FastAPI backend; 26 auth/limits; 28 hexagonal/12-factor | **template** [`fastapi-agent-service/`](../templates/README.md) |
| [`agents/`](#agents--agent-implementations) | Agent loop, framework variants, supervisor, **approval gates** | Ch 12 (§12.4), 16–18 (§18 Build), 17 (§17 Build), 20 (§20 Build) | 12 tool-loop; 16 reasoning; 17 supervisor; 18 three-ways; 20 approvals | [`agent-loop/`](../blueprints/agent-loop/PLAN.md) · [`multi-agent-supervisor/`](../blueprints/multi-agent-supervisor/PLAN.md) |
| [`rag/`](#rag--retrieval-pipeline) | chunk → embed → retrieve → rerank over private data | Ch 13 (§13 Build) | 13 RAG pipeline | [`rag-pipeline/`](../blueprints/rag-pipeline/PLAN.md) |
| [`memory/`](#memory--layered-memory) | Layered short/long-term memory + persistence | Ch 14 (§14 Build) | 14 layered memory | [`memory-module/`](../blueprints/memory-module/PLAN.md) |
| [`prompts/`](#prompts--versioned-prompt-registry-extends-appendix-c) | Versioned prompt templates + tiny registry **(extends Appendix C)** | Ch 10 (§10 Build) | 10 prompt techniques + testing | **template** prompt-template |
| [`llm/`](#llm--model-layer) | Base client, `structured.py`, **`gateway.py`** **(extends Appendix C)** | Ch 11 (§11 Build), 15 (§15 Build), 39–41 | 11 SDK shapes; 15 structured; 39 routing; 40 caching; 41 guards | [`llm-gateway/`](../blueprints/llm-gateway/PLAN.md) |
| [`security/`](#security--guardrails--policy-extends-appendix-c) | Guardrails, tool-permission tiers, sandbox, delegated auth, audit **(extends Appendix C)** | Ch 41 (§41 Build) | 41 injection defenses + guardrails | (in [`llm-gateway/`](../blueprints/llm-gateway/PLAN.md) guards + [`mcp-server/`](../blueprints/mcp-server/PLAN.md) scopes) |
| [`workers/`](#workers--celery-async--schedules) | Celery: async agent runs, beat schedules, outbox/idempotency | Ch 31 (§31 Build) | 31 Celery async + schedules | — *(see Ch 31; composes agent-loop)* |
| [`mcp/`](#mcp--mcp-server) | MCP server exposing platform tools + safe consumption | Ch 19 (§19 Build) | 19 build/consume MCP | [`mcp-server/`](../blueprints/mcp-server/PLAN.md) |
| [`web/`](#web--nextjs-frontend) | Next.js streaming chat UI, run timeline, approval cards | Ch 37–38 (§38 Build) | 38 streaming chat UI | **template** web-starter |
| [`evals/`](#evals--eval-harness--ci-gate) | Golden sets + graders + judge; CI quality gate | Ch 22 (§22 Build) | 22 eval harness + CI gate | [`eval-harness/`](../blueprints/eval-harness/PLAN.md) |
| [`observability/`](#observability--otel--dashboards) | OTel tracing of runs, token/cost accounting, dashboards, alerts | Ch 23 (§23 Build) | 23 tracing agent runs | [`observability-stack/`](../blueprints/observability-stack/PLAN.md) |
| [`infra/`](#infra--terraform) | Terraform: VPC, ECS/Fargate, RDS, ElastiCache, S3 | Ch 36 (§36.4) | 36 Terraform plan/apply | **template** terraform-module |
| [`.github/workflows/`](#githubworkflows--cicd) | CI/CD: tests, evals, build, deploy | Ch 7, 36 | 7 pytest + CI; 36 deploy pipeline | **template** github-actions-ci |
| [`docker-compose.yml` / `Dockerfile`](#docker--local-stack--image) | Full local stack; multi-stage shared api+worker image | Ch 35 (§35 Build) | 35 Dockerize a service | **template** dockerfile-and-compose |
| [`.env.example` / `pyproject.toml`](#config-roots) | Documented env vars; uv-managed deps | Ch 4, 28, 33 | 4 packaging; 28 12-factor config | — |

Notes on the table:
- **AWS deploy (Ch 33)** is not a single directory — it provisions and targets `infra/`,
  `app/`, and `workers/` for Fargate/RDS/ElastiCache/Bedrock. Its 🔧 Build (§33.10) produces
  the deploy notes + Terraform that `infra/` then codifies. Tracked as checkpoint
  `ch33-aws-deploy`.
- Three Build sections add code that is **cross-cutting** rather than a fresh directory:
  Ch 40 (cost/caching) lands inside `llm/gateway.py`; Ch 20 (approvals) lands inside
  `agents/` + the `app/` API; Ch 41 (security) spans `security/`, `mcp/` scopes, and the
  gateway guards. They still get their own checkpoints (the repo *state* changes), noted in
  [`checkpoints/PLAN.md`](checkpoints/PLAN.md).

---

## Per-directory detail

### `app/` — FastAPI backend
- **Purpose:** the platform's HTTP surface and its modular-monolith core — `main.py`
  (app factory, lifespan, routers), `api/` (runs, chats, documents routes with SSE),
  `core/` (Pydantic Settings, auth, deps), `domain/` (framework-free business logic),
  `db/` (SQLAlchemy models, sessions, `migrations/`), `services/` (orchestrates domain ↔
  adapters).
- **Built in:** Ch 25 (build the API), Ch 26 (authn/z, rate limits, multi-tenancy, webhooks),
  Ch 28 (hexagonal seams, 12-factor config, DI, health/shutdown). The data-layer wiring
  (`db/`) is fleshed out in Ch 30.
- **`learn/` walkthrough:** `25-*` (FastAPI backend), `26-*` (enterprise APIs),
  `28-*` (application architecture).
- **Pattern blueprint / template:** the [`fastapi-agent-service/`](../templates/README.md)
  **template** is the smallest version of this (copy-into-your-job scaffold); `app/` is the
  full assembled service.

### `agents/` — agent implementations
- **Purpose:** the platform's reasoning engines. `tools/` (tool schemas + safe executors),
  `raw/` (no-framework loop, the engine everything grows around), `graph/` (LangGraph
  variant), `pydantic_ai/` (Pydantic AI variant), `supervisor.py` (multi-agent supervisor
  that owns the goal + budget), and **`approvals.py`** — the human-in-the-loop wiring that
  gates risky tools by declared risk tier **(extends Appendix C: Ch 20 adds the approval
  gate into `agents/`)**.
- **Built in:** Ch 12 (§12.4 — `agents/raw/loop.py`), Ch 16 (reasoning patterns: ReAct,
  plan-execute, reflection), Ch 17 (§17 Build — `supervisor.py` + specialists), Ch 18
  (§18 Build — same agent in raw vs LangGraph vs Pydantic AI), Ch 20 (§20 Build — risk-tier
  table → approval gate in the loop, surfaced to the API/UI).
- **`learn/` walkthrough:** `12-*` (tool loop from scratch), `16-*` (reasoning),
  `17-*` (supervisor/workers), `18-*` (three frameworks), `20-*` (approval gates).
- **Pattern blueprints:** [`agent-loop/`](../blueprints/agent-loop/PLAN.md) (the framework-free
  loop, mirrors `agents/raw/`) and
  [`multi-agent-supervisor/`](../blueprints/multi-agent-supervisor/PLAN.md) (mirrors
  `agents/` orchestration).

### `rag/` — retrieval pipeline
- **Purpose:** retrieval over the private corpus. `ingest/` (loaders, chunking, embedding
  jobs), `stores/` (Chroma local + Pinecone cloud adapters behind one interface),
  `retrieve.py` (hybrid search + reranking). The `Retriever` protocol is the seam: agents and
  API routes depend on it, never on Chroma directly.
- **Built in:** Ch 13 (§13 Build). The `search_docs` tool that agents call is wired here and
  consumed in Part V.
- **`learn/` walkthrough:** `13-*` (chunk → embed → retrieve → rerank).
- **Pattern blueprint:** [`rag-pipeline/`](../blueprints/rag-pipeline/PLAN.md) (mirrors `rag/`).

### `memory/` — layered memory
- **Purpose:** the layered memory module — conversation buffers with token budgeting,
  summarization/compaction, long-term stores, recall ranking (relevance/recency/importance),
  and the state/persistence that lets long-running agents checkpoint and resume. Feeds the
  agent loop's message list.
- **Built in:** Ch 14 (§14 Build — wires the memory module into the capstone; the integration
  inventory pins this as §14.10).
- **`learn/` walkthrough:** `14-*` (layered memory).
- **Pattern blueprint:** [`memory-module/`](../blueprints/memory-module/PLAN.md) (mirrors `memory/`).

### `prompts/` — versioned prompt registry **(extends Appendix C)**
- **Purpose:** the platform keeps prompts as **versioned templates** loaded through a small
  registry, so a prompt is a tracked artifact (not a string buried in code) — the foundation
  for the "pin a prompt + tool + model triple" discipline Ch 44 formalizes.
- **Extends Appendix C:** Appendix C's tree implies prompts live with the model layer; Ch 10's
  §10 Build calls out a dedicated `prompts/` directory + registry. Listed here so the build
  plan matches the chapter.
- **Built in:** Ch 10 (§10 Build).
- **`learn/` walkthrough:** `10-*` (prompt techniques + prompt testing).
- **Template:** the prompt-template **template** is the copy-into-your-job version.

### `llm/` — model layer
- **Purpose:** the platform's **only door to model APIs**. Three pieces:
  - **`client.py`** — the base SDK client: one door with retries, streaming, usage accounting
    **(extends Appendix C: the Ch 11 base layer; Appendix C lists `llm/` with only
    `structured.py`)**.
  - `structured.py` — `complete_structured(prompt, schema)`: constrained decoding first, then
    validate-and-retry repair. The model choke point (in Appendix C).
  - **`gateway.py`** — wraps the client with routing-by-difficulty, fallback ladder, exact +
    semantic caching, cost-metering, and guards **(extends Appendix C: the Ch 39–41 layer)**.
- **Built in:** Ch 11 (§11 Build — `client.py`/`LLMClient`), Ch 15 (§15 Build —
  `structured.py`), Ch 39 (§39 Build — gateway routing/fallback), Ch 40 (§40 Build — caching +
  cost caps, lands in the gateway), Ch 41 (§41 Build — gateway guards, shared with `security/`).
- **`learn/` walkthrough:** `11-*` (SDK shapes/retries/caching), `15-*` (structured outputs),
  `39-*` (serving/routing), `40-*` (cost/caching).
- **Pattern blueprint:** [`llm-gateway/`](../blueprints/llm-gateway/PLAN.md) — the canonical
  blueprint for this whole directory (base client **plus** routing/fallbacks/cache/cost/guards;
  it supersedes the earlier `llm-client` name).

### `security/` — guardrails & policy **(extends Appendix C)**
- **Purpose:** the structural-safety layer: input/output **guardrails**, **tool-permission
  tiers**, **sandbox policy** for code execution, **delegated auth** (scoped, short-lived
  credentials for tools), and the **audit** trail. "Prompts ask; structure enforces" — this
  directory is the enforcement.
- **Extends Appendix C:** Appendix C folds security into individual layers; Ch 41's §41 Build
  consolidates the cross-cutting policy into a `security/` module (tiers + sandbox + audit) so
  the posture is one reviewable place. The gateway *guards* (in `llm/gateway.py`) and MCP tool
  *scopes* (in `mcp/`) are the enforcement points this module configures.
- **Built in:** Ch 41 (§41 Build).
- **`learn/` walkthrough:** `41-*` (prompt-injection defenses, guardrails, permission tiers).
- **Pattern blueprints:** the enforcement lives across
  [`llm-gateway/`](../blueprints/llm-gateway/PLAN.md) (guards) and
  [`mcp-server/`](../blueprints/mcp-server/PLAN.md) (tool scopes); no standalone `security`
  blueprint — it's a posture composed across them.

### `workers/` — Celery async + schedules
- **Purpose:** background execution. `celery_app.py` (the app + broker config), `tasks/`
  (async agent runs, scheduled automations via beat, outbox + idempotency). The key insight:
  **agent runs belong in the background** — the API stays thin and enqueues; workers do the
  long work and checkpoint.
- **Built in:** Ch 31 (§31 Build — Celery async runs + schedules; integration inventory pins
  §31.8). Idempotency/outbox patterns come from Ch 29.
- **`learn/` walkthrough:** `31-*` (Celery async + schedules).
- **Pattern blueprint:** — none dedicated; the worker *composes* the
  [`agent-loop/`](../blueprints/agent-loop/PLAN.md) behind a queue (see Ch 31).

### `mcp/` — MCP server
- **Purpose:** the platform's tool infrastructure exposed over the Model Context Protocol — a
  server publishing document search (backed by `rag/`), ticket lookup, and other enterprise
  capabilities, plus safe consumption of external MCP servers. Tool **scopes** declared here
  are an enforcement point for `security/`.
- **Built in:** Ch 19 (§19 Build).
- **`learn/` walkthrough:** `19-*` (build + consume an MCP server).
- **Pattern blueprint:** [`mcp-server/`](../blueprints/mcp-server/PLAN.md) (mirrors `mcp/`).

### `web/` — Next.js frontend
- **Purpose:** the user surface. `app/` (App Router pages: streaming chat UI, run timeline,
  tool-call + citation rendering, approval cards), `lib/` (API client, auth, SSE handling).
  TypeScript, Tailwind, shadcn/ui.
- **Built in:** Ch 37 (frontend essentials — TS/React/Next mental model), Ch 38 (§38 Build —
  the streaming chat workspace + live SSE from the backend).
- **`learn/` walkthrough:** `37-*` (frontend mental model), `38-*` (streaming chat UI).
- **Template:** the web-starter **template** is the copy-into-your-job scaffold; `web/` is the
  assembled app.

### `evals/` — eval harness & CI gate
- **Purpose:** the quality flywheel's *evaluate* station. `datasets/` (golden sets, versioned
  next to code), `run_evals.py` (code graders + calibrated LLM-judge + permission probes),
  wired into CI so a prompt/tool/model change that drops a gated metric does not merge.
- **Built in:** Ch 22 (§22 Build).
- **`learn/` walkthrough:** `22-*` (eval harness + CI gate).
- **Pattern blueprint:** [`eval-harness/`](../blueprints/eval-harness/PLAN.md) (mirrors `evals/`).

### `observability/` — OTel + dashboards
- **Purpose:** the nervous system. OTel setup, spans per model/tool call, token + dollar
  accounting per tenant, dashboards (up / fast / good / cost), alerts on SLO burn / spend rate
  / eval-score drops (symptom-based, not per-blip).
- **Built in:** Ch 23 (§23 Build).
- **`learn/` walkthrough:** `23-*` (tracing agent runs with OTel).
- **Pattern blueprint:** [`observability-stack/`](../blueprints/observability-stack/PLAN.md)
  (mirrors `observability/`).

### `infra/` — Terraform
- **Purpose:** infrastructure as code. `modules/` (reusable VPC/ECS/RDS/etc.),
  `envs/dev|prod/` (per-environment composition). Provisions the AWS target the platform
  deploys onto.
- **Built in:** Ch 36 (§36.4 — Terraform plan/apply). Targets the architecture stood up in
  Ch 33.
- **`learn/` walkthrough:** `36-*` (Terraform plan/apply, local via LocalStack/moto).
- **Template:** the terraform-module **template**.

### `.github/workflows/` — CI/CD
- **Purpose:** the automation rails — tests, evals (as a quality gate), build, and deploy.
- **Built in:** Ch 7 (pytest + CI foundations; `FakeLLM`, ruff/mypy gates), Ch 36 (deploy
  pipeline, reproducible + one-command rollback).
- **`learn/` walkthrough:** `7-*` (pytest + testing non-determinism), `36-*` (deploy pipeline).
- **Template:** the github-actions-ci **template**.

### Docker — local stack + image
- **Purpose:** `docker-compose.yml` brings up the full local stack (api, worker, postgres,
  redis, chroma); `Dockerfile` is multi-stage so the API and worker share one image.
- **Built in:** Ch 35 (§35 Build — Dockerize the service; containers & Kubernetes).
- **`learn/` walkthrough:** `35-*` (Dockerize a service).
- **Template:** the dockerfile-and-compose **template**.

### Config roots
- **Purpose:** `.env.example` documents every required variable (Pydantic Settings, fail-fast);
  `pyproject.toml` / `uv.lock` pin Python deps (uv). `core/config.py` (the `Settings` class) is
  first created in Ch 4 and is twelve-factor by Ch 28.
- **Built in:** Ch 4 (§4 Build — first real capstone code: `core/config.py`, `core/errors.py`,
  `core/logging.py`), Ch 28 (12-factor config), Ch 33 (deploy-time secrets via a manager).
- **`learn/` walkthrough:** `4-*` (packaging/config), `28-*` (12-factor).

---

## Build order (the spine)

The directories don't arrive at once; they accrete one chapter at a time (Gall's law — a
working complex system grows from a working simple one). The order:

1. **Foundations** (Part II): `core/config.py` + tests + CI rails (Ch 4, 7).
2. **Model layer** (Part III): `prompts/`, `llm/client.py` (Ch 10–11).
3. **Agent building blocks** (Part IV): `agents/raw/`, `rag/`, `memory/`, `llm/structured.py`
   (Ch 12–15).
4. **Orchestration** (Part V): `agents/supervisor.py`, framework variants, `mcp/`, approval
   gates (Ch 16–20).
5. **Quality** (Part VI): `evals/`, `observability/` (Ch 22–23).
6. **Backend** (Part VII): `app/`, `db/` data layer, `workers/` (Ch 25–31).
7. **Cloud** (Part VIII): `Dockerfile`/compose, `infra/`, deploy + CI/CD (Ch 33–36).
8. **Frontend** (Part IX): `web/` (Ch 37–38).
9. **Production hardening** (Part X): `llm/gateway.py`, `security/` (Ch 39–41).
10. **Assembly** (Part XI): Ch 44 — wire it all together, run the production-readiness
    checklist. No new directory; the system *becomes* production-grade here.

Each step ends at a checkpoint — see [`checkpoints/PLAN.md`](checkpoints/PLAN.md).
