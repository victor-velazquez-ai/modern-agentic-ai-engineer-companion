# Modern Agentic AI Engineer — Official Companion

The hands-on companion to the book **_Modern Agentic AI Engineer: A Full Handbook — From Zero to
Senior / Architect-Level Engineer_** by **Victor Miguel Velazquez Espitia**.

The book teaches *what* to build and *why*. This repository is where you **run it, break it, and keep
it** — a cell-by-cell learning lab (one folder per chapter), a shelf of professional blueprints, a
drawer of work-ready templates, and the complete reference capstone project, all mapped chapter by
chapter to the book.

> **The book's promise still holds: you build the capstone yourself.** This repo doesn't replace that
> work — it *supports* it. Run each chapter's notebooks to understand an idea by executing it, study a
> blueprint to see a production-grade version, start from a template, and use the **`capstone-project/`**
> reference to check your work *after* you've built your own. **Build first; compare second.** Typing
> and building beats cloning and pasting — every time. See [`docs/HOW-TO-USE.md`](docs/HOW-TO-USE.md).

> **Status: live.** Every chapter companion, blueprint, template, and the capstone is implemented and
> runs **offline in `MOCK` mode** (no API key, no cost) — verified in CI. Add a real key to run live.

---

## How the repo is organized — the chapter is the front door

Two axes, and no more, so it's easy to navigate:

| Folder | What it is | Use it to… |
|---|---|---|
| 📓 [`chapters-companion/`](chapters-companion/) | **One folder per book chapter** (`ch01-…` … `ch54-…`); Jupyter notebooks that teach the chapter's ideas **cell by cell**. The front door. | Understand a concept by executing it, experimenting, predicting outcomes. |
| 🧩 [`blueprints/`](blueprints/) | Self-contained, production-grade reference implementations of the recurring patterns and the book's use-case solutions. | Lift a real, adaptable version of a pattern into your own systems. |
| 🛠️ [`templates/`](templates/) | Minimal copy-me scaffolds (FastAPI agent service, project starter, ADR, CI, Terraform…). | Start a real project at work in minutes with sane defaults. |
| 🏗️ [`capstone-project/`](capstone-project/) | The complete, runnable **agentic-platform** reference (the book's running project) + per-Build **checkpoints**. | Build your own first — then diff against the reference to unblock yourself. |

Each chapter folder cross-links the **blueprint(s)** and **capstone checkpoint** it relates to, so you
can jump from "learn it" to "see it in production" in one hop.

---

## Chapter companions — the map (13 parts · 54 chapters)

Every chapter below is a folder in [`chapters-companion/`](chapters-companion/). Part overviews live in
[`chapters-companion/_parts/`](chapters-companion/_parts/).

- **Part 1 · Landscape & Mindset:** `ch01-why-agentic-ai` · `ch02-how-to-use-this-book` · `ch03-mental-model`
- **Part 2 · Software-Engineering Foundations:** `ch04-production-python` · `ch05-clean-code-and-design` · `ch06-data-structures-and-algorithms` · `ch07-version-control-testing-quality`
- **Part 3 · The LLM Substrate:** `ch08-how-llms-work` · `ch09-inference-sampling-control` · `ch10-prompt-engineering` · `ch11-working-with-model-apis`
- **Part 4 · Building Blocks of Agents:** `ch12-tool-use-and-function-calling` · `ch13-retrieval-augmented-generation` · `ch14-memory-and-state` · `ch15-structured-outputs-and-reliability`
- **Part 5 · Architectures & Orchestration:** `ch16-agent-reasoning-patterns` · `ch17-multi-agent-systems` · `ch18-framework-landscape` · `ch19-mcp-and-tool-ecosystems` · `ch20-human-in-the-loop`
- **Part 6 · Evaluation, Observability & Quality:** `ch21-quality-first` · `ch22-evaluation-and-quality` · `ch23-observability-for-agents`
- **Part 7 · Backend, APIs & Architecture:** `ch24-web-and-networking` · `ch25-building-apis-with-fastapi` · `ch26-apis-at-enterprise-grade` · `ch27-software-architecture-fundamentals` · `ch28-application-architecture` · `ch29-distributed-systems-fundamentals` · `ch30-data-layer` · `ch31-distributed-backends-and-automation`
- **Part 8 · Cloud & Infrastructure:** `ch32-cloud-foundations` · `ch33-aws-for-ai-engineers` · `ch34-azure-and-gcp` · `ch35-containers-and-kubernetes` · `ch36-infrastructure-as-code`
- **Part 9 · Frontend & Full-Stack:** `ch37-modern-frontend-essentials` · `ch38-building-ai-interfaces`
- **Part 10 · Production LLMOps:** `ch39-serving-and-scaling-models` · `ch40-cost-latency-performance` · `ch41-security-safety-compliance`
- **Part 11 · Architecting at Scale:** `ch42-system-design-for-ai` · `ch43-reference-architectures` · `ch44-capstone-end-to-end`
- **Part 12 · Specialized Frontiers:** `ch45-multimodal-agents` · `ch46-voice-and-realtime-agents` · `ch47-computer-use-and-browser-agents` · `ch48-customizing-models` · `ch49-frontier-and-staying-current`
- **Part 13 · Career & Leadership:** `ch50-career-ladder` · `ch51-senior-to-architect` · `ch52-interviews` · `ch53-brand-open-source-community` · `ch54-products-and-companies`

---

## Blueprints index — production-grade reference implementations

**Core pattern blueprints** (the recurring building blocks, referenced across the book):

| Blueprint | Pattern | Relates to |
|---|---|---|
| [`agent-loop`](blueprints/agent-loop/) | the perceive → decide → act → observe loop | Ch 12, 16 |
| [`llm-gateway`](blueprints/llm-gateway/) | provider-agnostic model gateway (retries, fallback, cost) | Ch 11, 40 |
| [`rag-pipeline`](blueprints/rag-pipeline/) | retrieval-augmented generation, end to end | Ch 13 |
| [`memory-module`](blueprints/memory-module/) | short- and long-term agent memory | Ch 14 |
| [`multi-agent-supervisor`](blueprints/multi-agent-supervisor/) | supervisor / worker orchestration | Ch 17 |
| [`mcp-server`](blueprints/mcp-server/) | a Model Context Protocol server | Ch 19 |
| [`eval-harness`](blueprints/eval-harness/) | offline + online agent evaluation | Ch 22 |
| [`observability-stack`](blueprints/observability-stack/) | tracing, metrics, logging for agents | Ch 23 |
| [`fastapi-agent-service`](blueprints/fastapi-agent-service/) | an agent behind a production API | Ch 25 |

**Use-case solution blueprints** — the book's Appendix-G "Agentic Use-Case Playbook," 12 sellable
solutions, each a reference build:

`customer-support-agent` · `document-extraction-pipeline` · `contract-review-assistant` ·
`compliance-monitoring-agent` · `incident-response-copilot` · `internal-knowledge-assistant` ·
`content-production-pipeline` · `product-copilot` · `research-due-diligence-agent` ·
`sales-revops-automation` · `software-engineering-agent` · `text-to-sql-analytics`
→ all in [`blueprints/`](blueprints/).

---

## Templates — copy-to-work scaffolds

`agent-project-starter` · `fastapi-agent-service` · `prompt-template` · `eval-dataset-template` ·
`adr-template` · `system-design-doc` · `dockerfile-and-compose` · `github-actions-ci` ·
`terraform-module` · `production-readiness-checklist` · `web-starter` → in [`templates/`](templates/).

---

## Quickstart

```bash
git clone https://github.com/victor-velazquez-ai/modern-agentic-ai-engineer-companion
cd modern-agentic-ai-engineer-companion
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Everything runs offline in MOCK mode — no API key, no cost:
jupyter lab chapters-companion/ch01-why-agentic-ai/
```

To run against real models, copy `.env.example` to `.env` and add a key (see
[`docs/SETUP.md`](docs/SETUP.md)). The capstone runs via `make` targets in
[`capstone-project/`](capstone-project/).

---

## Repository documentation

- [`docs/HOW-TO-USE.md`](docs/HOW-TO-USE.md) — the learner's guide: reading paths and how to use each
  part of the repo without falling into "paste, don't think."
- [`docs/SETUP.md`](docs/SETUP.md) — environment setup and running notebooks safely/cheaply.
- [`docs/REPO-PLAN.md`](docs/REPO-PLAN.md) — the master plan and chapter→asset map.
- [`docs/NOTEBOOK-STANDARDS.md`](docs/NOTEBOOK-STANDARDS.md) · [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — authoring standards.
- [`docs/BOOK-INTEGRATION.md`](docs/BOOK-INTEGRATION.md) — how the book's 2nd edition references this repo.

## License

Code, templates, and configuration are released under the [MIT License](LICENSE) — reuse them freely.
The teaching prose accompanies the book and remains © 2026 Victor Miguel Velazquez Espitia; it's here
for readers' personal learning. **The code is yours to use; the lessons are yours to learn from.**
