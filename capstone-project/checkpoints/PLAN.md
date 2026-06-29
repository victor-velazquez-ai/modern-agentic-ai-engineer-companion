# Checkpoints — the per-🔧-Build diff scheme

> Companion plan · `capstone/checkpoints/` · book Appendix C + every chapter with a 🔧 Build
> Status: 📋 planned (Phase 1)

## What a checkpoint is

A **checkpoint is the repo state at the end of one 🔧 Build section** — a known-good snapshot
of the `agentic-platform` after the code that Build adds. There is one per Build section, in
book order. Their single job is to let a reader **diff their own work** against a milestone:
when your Build doesn't run and you can't see why, `git diff` your tree against the matching
checkpoint and the delta is your bug.

> **Pedagogy (the whole point):** checkpoints exist so a stuck reader **compares instead of
> abandoning** the build — *not* so anyone skips ahead by checking one out and continuing from
> it. The rule from [`../README.md`](../README.md) holds: **build your section first; diff
> second.** A checkpoint is a mirror, not a shortcut.

### Shape (Phase 2)

Each checkpoint is the cumulative repo at that milestone (every earlier checkpoint's code plus
this Build's). Likely realization: a **tag/branch per checkpoint** on the capstone history
(`ckpt/ch12-tool-loop`, …) so a reader runs `git diff ckpt/ch12-tool-loop` from their own
repo, plus a short `NOTES.md` per checkpoint naming what's new and how to run/verify it. (Final
mechanism — orphan tags vs a `checkpoints/<id>/` snapshot tree — is a Phase-2 decision; the
*scheme* below is fixed now.)

---

## The ordered checkpoint list

23 checkpoints, in book order. "Adds" = the new code at that milestone (cumulative on the
prior one). "Maps to" = chapter · 🔧 Build · the capstone directory from
[`../PLAN.md`](../PLAN.md).

| # | Checkpoint | Maps to (Ch · Build) | What it adds |
|---|---|---|---|
| 1 | `ch12-tool-loop` | Ch 12 · §12.4 | `agents/raw/loop.py` — the framework-free tool-using loop; `agents/tools/` schemas + safe executors |
| 2 | `ch13-rag` | Ch 13 · §13 Build | `rag/` — ingest (chunk/embed), Chroma store, `retrieve.py` hybrid + rerank, `Retriever` protocol, `search_docs` tool |
| 3 | `ch14-memory` | Ch 14 · §14 Build (§14.10) | `memory/` — conversation buffer + token budgeting, summarization, long-term store, recall ranking, checkpoint/resume state |
| 4 | `ch15-structured` | Ch 15 · §15 Build | `llm/structured.py` — `complete_structured(prompt, schema)`: constrained decode → validate-and-retry repair |
| 5 | `ch17-supervisor` | Ch 17 · §17 Build | `agents/supervisor.py` + researcher/writer specialists; supervisor owns goal + budget |
| 6 | `ch18-three-ways` | Ch 18 · §18 Build | `agents/graph/` (LangGraph) + `agents/pydantic_ai/` — same agent slice, three frameworks |
| 7 | `ch19-mcp-server` | Ch 19 · §19 Build | `mcp/` — MCP server exposing document search + ticket tools; safe consumption of external servers |
| 8 | `ch20-approval-gates` | Ch 20 · §20 Build | `agents/approvals.py` — risk-tier table + approval gate in the loop; pause/resume surfaced to API |
| 9 | `ch22-eval-harness` | Ch 22 · §22 Build | `evals/` — golden `datasets/`, code graders + calibrated judge, permission probes, `run_evals.py` + CI gate |
| 10 | `ch23-observability` | Ch 23 · §23 Build | `observability/` — OTel spans per model/tool call, token+cost accounting per tenant, dashboards + alerts |
| 11 | `ch25-backend-api` | Ch 25 · §25 Build | `app/` — `main.py` factory/lifespan, `api/` routes (runs/chats/documents) with SSE, `core/` settings |
| 12 | `ch26-enterprise-api` | Ch 26 · §26 Build | `app/` authn/z, rate limits, multi-tenancy, webhooks |
| 13 | `ch28-app-architecture` | Ch 28 · §28 Build | hexagonal seams (`domain/` ports/adapters), 12-factor `core/config.py`, DI, health + graceful-shutdown contracts |
| 14 | `ch30-data-layer` | Ch 30 · §30 Build | `app/db/` — Postgres + pgvector models, sessions, `migrations/` (alembic), Redis caching, pooling |
| 15 | `ch31-workers-and-automation` | Ch 31 · §31 Build (§31.8) | `workers/` — `celery_app.py`, `tasks/` async agent runs, beat schedules, outbox + idempotency |
| 16 | `ch33-aws-deploy` | Ch 33 · §33.10 | deploy config targeting Fargate/RDS/ElastiCache/S3/Bedrock; secrets via manager; deploy notes |
| 17 | `ch35-containerized` | Ch 35 · §35 Build | `Dockerfile` (multi-stage, shared api+worker image) + `docker-compose.yml` (full local stack) |
| 18 | `ch36-infra-as-code` | Ch 36 · §36.4 | `infra/` — Terraform `modules/` + `envs/dev\|prod/`; `.github/workflows/` deploy + one-command rollback |
| 19 | `ch38-web-frontend` | Ch 38 · §38.5 | `web/` — Next.js streaming chat, run timeline, tool-call + citation render, approval cards, SSE client |
| 20 | `ch39-serving-and-gateway` | Ch 39 · §39 Build | `llm/gateway.py` — routing-by-difficulty + fallback ladder + circuit breakers over `llm/client.py` |
| 21 | `ch40-cost-and-caching` | Ch 40 · §40 Build | gateway exact + semantic caching; per-run/tenant/day budgets + hard caps; spend alarms (50/80/100%) |
| 22 | `ch41-security-and-guardrails` | Ch 41 · §41 Build | `security/` — guardrails, tool-permission tiers, sandbox policy, delegated auth, audit; gateway guards; MCP scopes |
| 23 | `ch44-production-readiness` *(final)* | Ch 44 · assembly | no new feature dir: end-to-end wiring, agent-version pinning (prompt+tool+model triple), the master readiness pass — the repo *complete* |

---

## Reconciliation against the consolidated list

The list above adjusts the prompt's consolidated list to match the **actual book source**.
Changes, each justified:

- **`ch10-prompts` and `ch11-llm-client` added implicitly?** — **No, kept out of the numbered
  list deliberately.** Ch 10 (`prompts/`) and Ch 11 (`llm/client.py`) *do* have 🔧 Build
  sections and *do* add capstone code (confirmed in source), and [`../PLAN.md`](../PLAN.md)
  maps them. They sit **before** `ch12-tool-loop`. The consolidated list began at `ch12`, so
  to honor it the canonical 23 start at Ch 12 — but Phase 2 should add **`ch10-prompts`** and
  **`ch11-llm-client`** as checkpoints 0a/0b for completeness (the directories exist and a
  reader builds them). *Flagged for the author.* Likewise Ch 4 (`core/config.py`) and Ch 7
  (CI rails) are early Build sections with capstone code; optionally checkpoint them too.
- **`ch16` (reasoning patterns)** — folded into `ch17-supervisor`, **not** its own checkpoint.
  Ch 16's loop variants (ReAct/plan-execute/reflection) extend `agents/raw/` but the chapter's
  Build culminates in the Ch 17 supervisor; matches the consolidated list (which skips 16).
- **`ch21` (quality-first)** — no checkpoint; it's the conceptual flywheel chapter (no
  capstone-code Build). The eval *code* arrives at `ch22-eval-harness`. Matches the list.
- **`ch24` / `ch27` / `ch29` / `ch32` / `ch34` / `ch37`** — no checkpoints; these are
  concept/foundation chapters (web & networking, architecture fundamentals, distributed-systems
  fundamentals, cloud foundations, Azure/GCP, frontend essentials). Their ideas land in the
  *next* directory-building chapter's checkpoint. Matches the list.
- **Section numbers `§NN Build`** — the prompt's list uses chapter granularity; where the
  [BOOK-INTEGRATION](../docs/BOOK-INTEGRATION.md) §2.4 inventory pins an exact subsection
  (§12.4, §14.10, §31.8, §33.10, §36.4, §38.5), this plan uses it. The rest are written
  `§NN Build` and get an exact number in Phase 3 when the callout is placed.

### ⚠️ Source-state note (important for Phase 2/3)

The current **1st-edition** draft contains an actual `#build[...]` callout in only **17
chapters** (4, 5, 6, 7, 10, 11, 12, 13, 15, 17, 18, 19, 20, 22, 38, 41, 42). Several chapters
that this scheme checkpoints — **14, 23, 25, 26, 28, 30, 31, 33, 35, 36, 39, 40** — wire the
capstone in *prose* but do **not yet have a `#build[` callout**. That is expected and
consistent with the plan:

- [BOOK-INTEGRATION.md](../docs/BOOK-INTEGRATION.md) §2.4 is explicit that the 🔧 Build
  inventory is *added/confirmed during the 2nd-edition pass* ("Confirm by grepping the source
  for the `#build[` opener before the pass"). These checkpoints correspond to the **planned**
  Build sections those chapters will carry once that pass lands the `#companion[...]` and
  `#build[...]` callouts.
- **Action for Phase 3:** when placing each `#companion[...]` callout (BOOK-INTEGRATION §2.4),
  ensure the chapter has a `#build[...]` Build section to anchor it, and give that Build the
  subsection number this table references. Re-grep `#build[` afterward and update any
  `§NN Build` here to the exact `§NN.x`.
- **Ch 42 has a `#build[` but no capstone checkpoint** — by design: §42.7 builds a *paper*
  system-design exercise (a worked B2B support design), not capstone code, so it feeds the
  system-design **template**, not a capstone directory. Noted so the count (42 has a Build, but
  no `ch42-*` checkpoint) is not read as an omission.
- **Ch 44 is the only "no new code" checkpoint** — `ch44-production-readiness` snapshots the
  *assembled, hardened* repo and the production-readiness checklist run; it adds wiring and the
  agent-versioning discipline, not a fresh feature directory.

---

## How a reader uses these (the loop)

1. Reach the chapter's 🔧 Build; **build the piece in your own repo.**
2. Run it. If it works, optionally skim the matching checkpoint to compare structure.
3. If it doesn't, **`git diff` your tree against the checkpoint** (`git diff ckpt/<id>`), find
   the single difference, fix *that* in your code.
4. Read the checkpoint's `NOTES.md` for the "what's new + how to verify" so you confirm your
   own version behaves the same.
5. Move on. Never continue *from* a checked-out checkpoint — the platform you can explain is the
   one **you** built.
