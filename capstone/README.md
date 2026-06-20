# 🏗️ Capstone — the complete `agentic-platform`

This is the full, runnable reference implementation of the book's running project: a
general-purpose **multi-agent platform** (RAG over private data, tool-using agents, MCP
integrations, scheduled automations, async runs, a FastAPI backend, a Next.js frontend,
deployed on AWS, with evals, observability, and guardrails). It is the realization of the
book's **Appendix C** — the finished structure you are building *toward*.

> **Status:** 📋 planning skeleton (Phase 1). This folder currently holds plans only —
> [`PLAN.md`](PLAN.md) (the directory-by-directory build plan) and
> [`checkpoints/PLAN.md`](checkpoints/PLAN.md) (the per-Build checkpoint scheme). The source
> tree and `checkpoints/` snapshots land in Phase 2.

---

## ⚠️ The one rule: build yours first, then compare

The book's promise — and the reason it works — is **you build the capstone yourself**, one
🔧 *Build* section at a time, typing the code into *your* editor. Typing and assembling is
what turns reading into understanding; cloning and pasting never does. So read this folder
the right way:

> **This is the reference + answer key, not a starting point to clone.** Build your own
> platform from the book's Build sections. Use this to **check your work, compare
> approaches, and unblock** when a section leaves you stuck — never to skip the building.

Concretely, the intended loop for every Build section is:

1. **Build it yourself** from the chapter's 🔧 Build section — your code, your repo.
2. **Compare** against the matching directory here once yours runs (or once you're stuck on
   *why* yours doesn't).
3. **Diff against a checkpoint** ([`checkpoints/`](checkpoints/PLAN.md)) — each checkpoint is
   the repo state at the end of one Build section, so you can `git diff` your work against a
   known-good milestone instead of abandoning the build.

If you find yourself copying a whole directory before you've tried to write it, stop — you're
spending the book's core asset (the building) to save an hour. The
[pedagogy guardrail](../docs/REPO-PLAN.md#the-pedagogy-guardrail-read-this-before-adding-anything)
is the contract; this README is its front door for the capstone.

---

## Repository structure (Appendix C, faithfully)

The layout you arrive at. This reproduces Appendix C's tree; the directories marked
**(extends Appendix C)** are additions the chapters introduce and that
[`PLAN.md`](PLAN.md) maps in full.

```text
agentic-platform/
├── app/                      # FastAPI backend (Ch 25–26, 28)
│   ├── main.py               #   app factory, lifespan, routers
│   ├── api/                  #   route modules (runs, chats, documents)
│   ├── core/                 #   settings (Pydantic Settings), auth, deps
│   ├── domain/               #   business logic — framework-free
│   ├── db/                   #   SQLAlchemy models, sessions, migrations/
│   └── services/             #   orchestration between domain and adapters
├── agents/                   # agent implementations (Ch 12, 16–18, 20)
│   ├── tools/                #   tool schemas + safe executors
│   ├── raw/                  #   no-framework agent loop (Ch 12)
│   ├── graph/                #   LangGraph version (Ch 18)
│   ├── pydantic_ai/          #   Pydantic AI version (Ch 18)
│   ├── approvals.py          #   approval gates / human-in-the-loop (Ch 20)  ← extends Appendix C
│   └── supervisor.py         #   multi-agent supervisor (Ch 17)
├── rag/                      # retrieval pipeline (Ch 13)
│   ├── ingest/               #   loaders, chunking, embedding jobs
│   ├── stores/               #   Chroma (local) + Pinecone (cloud) adapters
│   └── retrieve.py           #   hybrid search + reranking
├── memory/                   # layered memory module (Ch 14)
├── prompts/                  # versioned prompt registry (Ch 10)               ← extends Appendix C
├── llm/                      # model layer (Ch 11, 15, 39–41)
│   ├── client.py             #   base SDK client: retries, streaming, usage (Ch 11)  ← extends Appendix C
│   ├── structured.py         #   complete_structured: the model choke point (Ch 15)
│   └── gateway.py            #   routing, fallback, cache, cost, guards (Ch 39–41)     ← extends Appendix C
├── security/                 # guardrails, permission tiers, sandbox, audit (Ch 41)   ← extends Appendix C
├── workers/                  # Celery app: async runs, schedules (Ch 31)
│   ├── celery_app.py
│   └── tasks/
├── mcp/                      # MCP server exposing platform tools (Ch 19)
├── web/                      # Next.js frontend (Ch 37–38)
│   ├── app/                  #   App Router pages, streaming chat UI
│   └── lib/                  #   API client, auth, SSE handling
├── evals/                    # eval harness + golden sets (Ch 22)
│   ├── datasets/
│   └── run_evals.py          #   also wired into CI as a quality gate
├── infra/                    # Terraform: VPC, ECS, RDS, etc. (Ch 36)
│   ├── modules/
│   └── envs/dev|prod/
├── observability/            # OTel setup, dashboards, alerts (Ch 23)
├── .github/workflows/        # CI/CD: tests, evals, build, deploy (Ch 7, 36)
├── docker-compose.yml        # full local stack (below)
├── Dockerfile                # multi-stage: api + worker share one image
├── pyproject.toml / uv.lock  # Python deps (uv)
└── .env.example              # every required variable, documented
```

The repo is deliberately a **modular monolith** (Ch 27–28): one deployable, strict module
boundaries, `domain/` importing nothing from the web or worker layers. When a Build section
says "extract this," that seam is where it pays off.

---

## Running it locally

Once *you* have built it, one command brings up the whole stack — API, Celery worker,
Postgres (with pgvector), Redis (broker + cache), and Chroma. This is the run procedure from
Appendix C; the code came from the Build sections, not a download:

```bash
git clone git@github.com:your-username/agentic-platform.git   # YOUR repo
cd agentic-platform
cp .env.example .env          # fill in ANTHROPIC_API_KEY at minimum
docker compose up -d --build  # api, worker, postgres, redis, chroma
docker compose exec api alembic upgrade head   # run DB migrations
curl localhost:8000/health    # {"status":"ok"}

cd web && corepack pnpm install && pnpm dev    # frontend on :3000
```

### Dev workflow (fast reload)

Day-to-day, run the stateful services in Docker and the code you're editing on the host:

```bash
docker compose up -d postgres redis chroma     # just the stateful services
uv run fastapi dev app/main.py                 # API with hot reload
uv run celery -A workers.celery_app worker     # worker with the same code
```

---

## Environment variables

`.env.example` is the source of truth; settings load via **Pydantic Settings** (Ch 28) and
**fail fast** when a required one is missing. (The repo-wide `COMPANION_MOCK` switch lives in
the top-level [`.env.example`](../.env.example) and lets notebooks run free/offline; the
capstone reads provider keys directly per Appendix C.)

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Primary model provider (**required**) |
| `OPENAI_API_KEY` | Secondary provider for routing / eval-judge chapters |
| `DATABASE_URL` | Postgres DSN; compose default points at the local container |
| `REDIS_URL` | Celery broker, result backend, and cache |
| `CHROMA_URL` / `PINECONE_API_KEY` | Vector store — local default / cloud option |
| `AUTH_SECRET` | JWT signing secret for the web app |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Where traces go (Langfuse / Phoenix / self-hosted collector) |
| `AWS_PROFILE` / `AWS_REGION` | Only needed for the deploy chapters (Part VIII) |

---

## How to use this reference without cheating yourself

A short discipline so the answer key stays an asset, not a crutch:

- **Write the Build section first — always.** Open the chapter's 🔧 Build, build the piece in
  your own repo, get it running. Only then open the matching directory here.
- **When stuck, diff — don't replace.** `git diff` your file against the matching
  [checkpoint](checkpoints/PLAN.md) to find the *one* thing that's off. Fix that line in your
  code; don't paste the whole file.
- **Read by comparing, not copying.** The value is in the delta between your design and this
  one — *why* the seam is here, *why* the protocol sits there. Note the differences; that's
  the senior-level lesson.
- **Treat blueprints as the "pattern," this as the "assembled system."** A
  [blueprint](../blueprints/README.md) shows one mechanism in isolation (the part); the
  capstone shows how the parts wire into a whole. Study the blueprint to learn the pattern;
  consult the capstone to see it integrated.
- **Lift ideas, not implementations.** Adapt the structure to your own problem. The goal is a
  platform you can explain end to end — which only happens if you built it.

> If you only ever clone and run this, you'll have a working demo and none of the judgment the
> book exists to teach. Build first; compare second.

---

## Where this maps in the book

- **Appendix C** — the canonical directory map, run commands, and env vars (the source of
  truth this README reproduces).
- **Chapter 44** — the end-to-end assembly walkthrough + the master production-readiness
  checklist; read it twice (once now, once before you ship your own).
- **Chapter 2** — *How to Use This Book*: the "build it yourself" stance this folder honors.
- [`PLAN.md`](PLAN.md) — the directory-by-directory build plan (which chapter builds what,
  and the blueprint/walkthrough each directory mirrors).
- [`checkpoints/PLAN.md`](checkpoints/PLAN.md) — the per-🔧-Build checkpoint scheme (the
  diff targets).
