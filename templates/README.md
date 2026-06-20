# 🛠️ Templates — work-ready scaffolds

The smallest useful **starting point** for a new project, designed to be **copied straight
into your job**. A template is sane defaults + TODO markers + *no business logic* — the
folder you clone on Monday morning so you start with production hygiene already in place
instead of a blank directory and a `requirements.txt` you assemble from memory.

> **The rule: copy the folder, fill the TODOs, never commit secrets.** Unlike `blueprints/`
> (which you *study and adapt*) and `learn/` (which you *run to understand*), templates are
> meant to be **taken**. Copy `templates/<name>/` into your repo, search for `TODO`/`▢`,
> replace the placeholders, and delete this notice. Every template reads secrets **only**
> from `.env` (git-ignored) — there are no keys in any committed file, and there never
> should be in yours. See [`../docs/CONVENTIONS.md`](../docs/CONVENTIONS.md) and
> [`../docs/REPO-PLAN.md`](../docs/REPO-PLAN.md) §2.

These do **not** undercut the book's "build it yourself" promise: a template gives you the
*boilerplate* (the parts that are the same in every project and worth standardizing), never
the *agent logic* (the parts the book teaches you to build). You still write the interesting
code — the template just means you write it inside a project that lints, types, tests, and
ships from commit one.

---

## The catalog

Eleven templates. The slugs are **canonical** — chapter and capstone plans link to exactly
these names. "Copy when you need to…" is the at-work trigger that should make you reach for it.

| Template | What it scaffolds | Realizes (Ch) | Copy when you need to… |
|---|---|---|---|
| [`agent-project-starter/`](agent-project-starter/PLAN.md) | A minimal, well-structured Python agent project: `pyproject` + `src/` layout, LLM access, one example tool, tests, `.env.example`, `Makefile` | 4, 11, 12 | …start *any* new Python agent/LLM project from a clean, typed, tested base |
| [`fastapi-agent-service/`](fastapi-agent-service/PLAN.md) | A FastAPI service exposing an agent: routers, Pydantic Settings, DI, SSE streaming, `/health`, Dockerfile | 25, 26, 28 | …stand up an HTTP/streaming API in front of an agent |
| [`prompt-template/`](prompt-template/PLAN.md) | A versioned prompt file/registry layout: system + user templates, version dirs, a render+regression test | 10 | …take a prompt out of an f-string and put it under version control |
| [`eval-dataset-template/`](eval-dataset-template/PLAN.md) | A tagged golden-set JSONL schema + a scorer stub + dataset folder layout | 22 | …start measuring an LLM feature instead of vibe-checking it |
| [`adr-template/`](adr-template/PLAN.md) | An Architecture Decision Record markdown template (context · decision · alternatives · consequences) | 27 | …record *why* you chose something, the moment you choose it |
| [`system-design-doc/`](system-design-doc/PLAN.md) | An AI system-design doc: requirements · constraints · back-of-envelope estimation · architecture · ADR log | 42 | …design a feature/service before you build it (or in an interview) |
| [`production-readiness-checklist/`](production-readiness-checklist/PLAN.md) | The copy-into-your-repo go-live checklist (from Appendix F) | 41, 44 | …gate a launch on the things that actually break in prod |
| [`github-actions-ci/`](github-actions-ci/PLAN.md) | A CI workflow scaffold: lint → type-check → test → **eval-gate** | 7, 22, 36 | …add CI that also blocks on agent-quality regressions, not just unit tests |
| [`dockerfile-and-compose/`](dockerfile-and-compose/PLAN.md) | A multi-stage Dockerfile + `docker-compose` (api + worker + postgres + redis + chroma) | 35 | …containerize a service and bring its whole local stack up with one command |
| [`terraform-module/`](terraform-module/PLAN.md) | A reusable Terraform module skeleton: `variables`/`outputs`/`main` + `envs/dev\|prod` | 36 | …write infra you can reuse across environments instead of click-ops |
| [`web-starter/`](web-starter/PLAN.md) | A Next.js App Router + TypeScript + Tailwind + Vercel AI SDK streaming-chat starter | 37, 38 | …put a streaming chat UI in front of your agent backend |

---

## How a template relates to the other pillars

A template is the **starting** shape; a blueprint is the **hardened** shape; the capstone is
the **assembled** shape. Several templates are the empty-project version of a capstone
directory you fill in as the book progresses:

| Template | Mirrors capstone dir | Related blueprint | The relationship |
|---|---|---|---|
| `agent-project-starter` | (project root) | [`../blueprints/agent-loop/`](../blueprints/agent-loop/PLAN.md) | the empty project; the agent *logic* you add is what `agent-loop` shows hardened |
| `fastapi-agent-service` | [`app/`](../../chapters/92-appendix-capstone.typ) | [`../blueprints/agent-loop/`](../blueprints/agent-loop/PLAN.md) | the API shell the capstone's `app/` grows from |
| `prompt-template` | `llm/` (prompt assets) | [`../blueprints/llm-gateway/`](../blueprints/llm-gateway/PLAN.md) | where the gateway's prompts live, versioned |
| `eval-dataset-template` | `evals/datasets/` | [`../blueprints/eval-harness/`](../blueprints/eval-harness/PLAN.md) | the dataset the harness scores |
| `github-actions-ci` | `.github/workflows/` | [`../blueprints/eval-harness/`](../blueprints/eval-harness/PLAN.md) | the pipeline that runs the harness as a gate |
| `dockerfile-and-compose` | `Dockerfile`, `docker-compose.yml` | — | the capstone's local-stack definition, generalized |
| `terraform-module` | `infra/modules/`, `infra/envs/` | — | the reusable unit the capstone's `infra/` is built from |
| `web-starter` | `web/` | — | the frontend shell the capstone's `web/` grows from |

The book's architecture chapters (Ch 27–28, 42) and the career chapters (Ch 50–52) also point
at the doc templates — `adr-template`, `system-design-doc`, `production-readiness-checklist` —
as the artifacts a senior/architect produces, not just code.

---

## Using one (Phase 2)

```bash
# 1. copy the scaffold into your project (not a submodule — you own it now)
cp -r templates/agent-project-starter ~/work/my-new-agent && cd ~/work/my-new-agent

# 2. find every placeholder and replace it
grep -rn "TODO" .            # or open in your editor and search TODO / ▢

# 3. wire your secrets — from the environment, never committed
cp .env.example .env         # fill in real values; .env is git-ignored

# 4. confirm the scaffold runs/builds before you add business logic
make check                   # (per-template; see each PLAN's "definition of done")
```

---

## Status

📋 **Phase 1 — planning.** Each folder currently holds a `PLAN.md` only — the exact file tree,
baked-in defaults, and book mapping that Phase 2 will realize as a copyable scaffold. Phase 2
fills in the actual files (each one verified to run/build after its TODOs are filled, with **no
secrets committed**). See [`../docs/REPO-PLAN.md`](../docs/REPO-PLAN.md) §5.
