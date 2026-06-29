# Master Plan — Modern Agentic AI Engineer Companion

> This is the **blueprint for the repository itself**: the vision, the asset taxonomy, the
> full structure, the chapter→asset map, and the process for building it all in Phase 2.
> If you only read one document, read this one.

---

## 1. Why this repo exists

The book *Modern Agentic AI Engineer* is a 500+ page path from capable coder to
architect-level AI engineer. It is deliberately a **book you build alongside** — its spine
is a running capstone project (a general-purpose multi-agent platform) that the reader
assembles, one 🔧 *Build* section at a time.

A book, though, can only print code; it can't let you **run** it. This companion closes that
gap and turns the book into three things at once:

1. **A learning lab** — every important idea becomes a notebook you execute cell by cell,
   change, and predict. Reading teaches *what*; running teaches *how*.
2. **A reference shelf** — professional blueprints and the complete capstone, to consult
   "anytime you're facing a challenge" long after the first read.
3. **A working toolkit** — templates you copy straight into your job to start real projects
   with production defaults already in place.

The goal stated by the author: make the book "not just a knowledge book, but a whole
**learning bible**, a **reference book**, and a **course** — a game-changer for students."

### The pedagogy guardrail (read this before adding anything)

The book's core promise is **"you build the capstone yourself."** That promise is *why* the
book works — typing and building creates understanding that cloning and pasting never will.
This repo must reinforce that, not undercut it. Concretely:

- **`chapters-companion/` notebooks** teach *concepts in isolation* — sandboxes and experiments, not the
  capstone handed over. You run them to understand, then go build the real thing.
- **`blueprints/`** are *adaptable reference patterns*, framed as "study and lift," not
  "the answer to copy."
- **`capstone-project/`** is the **complete reference implementation** — present (the author chose
  maximal completeness) but framed throughout as **"build yours first, then compare"**: an
  answer key and an unblocking aid, with `checkpoints/` that match each Build section so a
  stuck reader can diff against a known-good state rather than abandon the build.

Every asset we author should pass this test: *does it help the reader build and understand,
or does it tempt them to skip the building?* If the latter, reframe it.

---

## 2. The asset taxonomy

Four pillars, each with a precise definition so we never blur them.

### 📓 Learn — chapter notebooks (`chapters-companion/`)
One folder per book chapter, mirroring the book's parts. Each holds one or more Jupyter
notebooks of two flavors:

- **Concept lab** — runnable theory. Takes an idea from the chapter (attention, sampling,
  chunking, CAP, idempotency) and makes it tangible with small, fast, mostly-offline cells.
- **Walkthrough** — a guided build of *one* mechanism from the chapter (a tool-use loop, a
  retriever, an eval scorer) in isolation, end to end, with the chapter's pitfalls called
  out inline.

Notebooks are the **teaching** surface. They are heavy on markdown narration, prediction
prompts, and "now change this and rerun" moments.

### 🧩 Blueprints — reference implementations (`blueprints/`)
Self-contained, production-grade implementations of the **recurring patterns** the book
returns to. Not notebooks — real modules with tests, a README, and a tiny runnable demo.
Examples: a hybrid RAG pipeline, an eval harness with golden sets, an MCP server, a layered
memory module, a multi-agent supervisor, an OTel observability stack. A reader **studies and
adapts** these; they're the "how a senior would actually structure this" reference.

### 🛠️ Templates — work-ready scaffolds (`templates/`)
The smallest useful starting point for a *new* project, designed to be **copied into your
job**. Sane defaults, TODO markers, no business logic. Examples: a FastAPI agent service, an
agent project starter, an ADR template, an eval dataset template, a system-design doc, a CI
pipeline, a Terraform module, a prompt file. Optimized for "clone this folder and go."

### 🏗️ Capstone — the complete platform (`capstone-project/`)
The full, runnable **agentic-platform** — the realization of the book's Appendix C. This is
the dedicated home for the finished reference project, plus:

- **`checkpoints/`** — the repo state at the end of each 🔧 Build section, so a reader can
  diff their own work against a known-good milestone (the "answer key").

Framed everywhere as: *build your own from the Build sections; use this to check, compare,
and unblock — not to replace the work.*

---

## 3. Full repository structure

```text
modern-agentic-ai-engineer-companion/
├── README.md                     # front door + status
├── LICENSE                       # MIT (code) + note on prose
├── CHANGELOG.md                  # per-phase changelog
├── .gitignore
├── .env.example                  # every env var the notebooks/capstone use
├── requirements.txt              # Python deps baseline for notebooks (Phase 2)
├── docs/
│   ├── REPO-PLAN.md              # ← this file (the master plan)
│   ├── BOOK-INTEGRATION.md       # how the 2nd edition references the repo + republish checklist
│   ├── HOW-TO-USE.md             # learner's guide & reading paths
│   ├── SETUP.md                  # environment, API keys, cost-free mock modes
│   ├── NOTEBOOK-STANDARDS.md     # the authoring standard for every notebook
│   └── CONVENTIONS.md            # naming + the canonical PLAN.md template + callouts
├── chapters-companion/                        # 📓 per-chapter notebooks (mirrors the book)
│   ├── part-01-landscape-and-mindset/
│   │   ├── README.md             #   part overview + chapter index
│   │   ├── 01-why-agentic-ai/PLAN.md
│   │   ├── 02-how-to-use-this-book/PLAN.md
│   │   └── 03-mental-model/PLAN.md
│   ├── part-02-software-engineering-foundations/    # Ch 4–7
│   ├── part-03-llm-substrate/                        # Ch 8–11
│   ├── part-04-building-blocks-of-agents/            # Ch 12–15
│   ├── part-05-architectures-and-orchestration/      # Ch 16–20
│   ├── part-06-evaluation-observability-quality/     # Ch 21–23
│   ├── part-07-backend-apis-architecture/            # Ch 24–31
│   ├── part-08-cloud-and-infrastructure/             # Ch 32–36
│   ├── part-09-frontend-and-fullstack/               # Ch 37–38
│   ├── part-10-production-llmops/                    # Ch 39–41
│   ├── part-11-architecting-at-scale/                # Ch 42–44
│   ├── part-12-specialized-frontiers/                # Ch 45–49
│   ├── part-13-career-and-leadership/                # Ch 50–54
│   └── appendices/PLAN.md                            # A–G → companion assets map
├── blueprints/
│   ├── README.md                 # catalog of blueprints
│   └── <one folder per blueprint>/PLAN.md
├── templates/
│   ├── README.md                 # catalog of templates
│   └── <one folder per template>/PLAN.md
└── capstone-project/
    ├── README.md                 # what the capstone is + Appendix C mapping
    ├── PLAN.md                   # directory-by-directory build plan
    └── checkpoints/PLAN.md       # per-Build checkpoint scheme
```

Every leaf folder carries a `PLAN.md` in Phase 1; Phase 2 fills in the notebooks/code.

---

## 4. The chapter → asset map (overview)

Detail lives in each chapter's `PLAN.md`; this is the bird's-eye view. "Notebooks" is the
*planned* count and intent; "Feeds" shows which blueprints/templates/capstone dirs the
chapter contributes to.

| Part | Ch | Title | Companion emphasis |
|---|---|---|---|
| I | 1 | Why Agentic AI | Concept/orientation — 1 notebook (the agent loop, minimal) |
| I | 2 | How to Use This Book | Orientation — how to use *this repo* alongside it |
| I | 3 | Mental Model | Concept lab — the four planes, traced through a live request |
| II | 4 | Production Python | Concept labs — typing, async, packaging drills |
| II | 5 | Clean Code & Design | Refactoring drills + patterns you'll reuse |
| II | 6 | DS&A (that matter) | Big-O intuition + the structures AI systems use |
| II | 7 | Version Control, Testing & Quality | pytest + testing non-determinism → CI template |
| III | 8 | How LLMs Work | Concept labs — tokenizers, embeddings, attention intuition |
| III | 9 | Inference & Sampling | Concept lab — temperature/top-p/seeds, live decoding |
| III | 10 | Prompt Engineering | Walkthroughs — techniques + prompt testing → prompt template |
| III | 11 | Working with Model APIs | Walkthrough — SDK shapes, retries, caching → llm blueprint |
| IV | 12 | Tool Use & Function Calling | Walkthrough — tool loop from scratch → agent-loop blueprint, capstone `agents/raw` |
| IV | 13 | RAG | Walkthroughs — chunk→embed→retrieve→rerank → rag-pipeline blueprint, capstone `rag/` |
| IV | 14 | Memory & State | Walkthrough — layered memory → memory-module blueprint, capstone `memory/` |
| IV | 15 | Structured Outputs & Reliability | Walkthrough — schema-first + repair → capstone `llm/structured` |
| V | 16 | Reasoning Patterns | Walkthroughs — ReAct, plan-execute, reflection |
| V | 17 | Multi-Agent Systems | Walkthrough — supervisor/workers → multi-agent-supervisor blueprint, capstone `agents/` |
| V | 18 | Framework Landscape | Walkthrough — same agent in raw vs LangGraph vs Pydantic AI |
| V | 19 | MCP & Tool Ecosystems | Walkthrough — build/consume an MCP server → mcp-server blueprint, capstone `mcp/` |
| V | 20 | Human-in-the-Loop | Walkthrough — approval gates for risky tools |
| VI | 21 | Quality-First | Concept — the quality flywheel, instrumented |
| VI | 22 | Evaluation & Quality | Walkthrough — eval harness + CI gate → eval-harness blueprint, capstone `evals/` |
| VI | 23 | Observability | Walkthrough — tracing agent runs with OTel → observability-stack blueprint |
| VII | 24 | Web & Networking | Concept labs — HTTP, idempotency, the request lifecycle |
| VII | 25 | FastAPI | Walkthrough — build the backend API → fastapi-agent-service template, capstone `app/` |
| VII | 26 | Enterprise APIs | Walkthroughs — authn/z, rate limits, webhooks |
| VII | 27 | Software Architecture Fundamentals | Concept — quality attributes, ADRs, C4 → adr + system-design templates |
| VII | 28 | Application Architecture | Concept/walkthrough — hexagonal, 12-factor, DI |
| VII | 29 | Distributed Systems Fundamentals | Concept labs — CAP, retries, idempotency, sagas (simulated) |
| VII | 30 | Data Layer | Walkthroughs — Postgres/pgvector, Redis caching, access patterns |
| VII | 31 | Distributed Backends & Automation | Walkthrough — Celery async runs + schedules → capstone `workers/` |
| VIII | 32 | Cloud Foundations | Concept — the cloud mental model, FinOps |
| VIII | 33 | AWS for AI Engineers | Walkthroughs (mostly `moto`/LocalStack) → capstone deploy notes |
| VIII | 34 | Azure & GCP | Concept — parity + portability |
| VIII | 35 | Containers & Kubernetes | Walkthrough — Dockerize a service → dockerfile/compose template |
| VIII | 36 | Infrastructure as Code | Walkthrough — Terraform plan/apply (local) → terraform-module template, capstone `infra/` |
| IX | 37 | Modern Frontend Essentials | Concept — TS/React/Next mental model (TS notebooks/Deno) |
| IX | 38 | Building AI Interfaces | Walkthrough — streaming chat UI → web template, capstone `web/` |
| X | 39 | Serving & Scaling Models | Walkthroughs — routing/fallbacks, batching (mock + optional local) |
| X | 40 | Cost, Latency & Performance | Concept lab — token accounting, semantic cache |
| X | 41 | Security, Safety & Compliance | Walkthrough — prompt-injection defenses, guardrails |
| XI | 42 | System Design for AI | Concept — the method + back-of-envelope estimation → system-design template |
| XI | 43 | Reference Architectures | Concept — case studies → blueprint cross-links |
| XI | 44 | Capstone End-to-End | The full `capstone-project/` walkthrough + production-readiness pass |
| XII | 45 | Multimodal Agents | Walkthrough — vision/document extraction |
| XII | 46 | Voice & Realtime | Walkthrough — realtime/turn-taking (mockable) |
| XII | 47 | Computer-Use & Browser Agents | Walkthrough — browser automation, sandboxed |
| XII | 48 | Customizing Models | Concept/walkthrough — fine-tune vs RAG vs prompt; LoRA (small/local) |
| XII | 49 | The Frontier | Reference — reading papers, tracking the field (no code) |
| XIII | 50 | Career Ladder | Reference/worksheet — skill-matrix, portfolio plan |
| XIII | 51 | Senior → Architect | Reference — ADR/RFC practice → templates cross-link |
| XIII | 52 | Interviews | Worksheets — system-design drills, rubrics |
| XIII | 53 | Brand, OSS, Community | Reference — checklists |
| XIII | 54 | Products & Companies | Worksheet — the 12–24 month roadmap |

**Appendices** map to companion assets rather than chapters: A (toolchain) → `docs/SETUP.md`;
B (cheat sheets) → quick-reference notebooks/`templates/`; C (capstone map) → `capstone-project/`;
D (resources) → curated links; E (glossary) → reference; F (master checklist) → checklist
template; G (use-case playbook) → a set of `blueprints/`. Detail in
[`chapters-companion/appendices/PLAN.md`](../chapters-companion/appendices/PLAN.md).

> **Note on "no-code" chapters.** Some chapters (e.g., 2, 49, 50, 53) are intentionally
> reference/worksheet-only — their `PLAN.md` says so and explains why. Completeness means the
> *right* asset per chapter, not a forced notebook everywhere.

---

## 5. Phases & process

### Phase 1 — Plan (this deliverable) ✅
Full structure + a `PLAN.md` per chapter and asset, all consistent with the book. Pushed
public so it's a living, reviewable plan.

### Phase 2 — Build
Implement the assets the plans describe. Process (following the book's own
[PLAYBOOK](https://github.com/victor-velazquez-ai/ai-book-creation)):

1. **Lock standards first** — `NOTEBOOK-STANDARDS.md` + `CONVENTIONS.md` are the contract.
2. **Build the blueprints and capstone core early** — notebooks import from them, so they're
   the foundation. (A walkthrough notebook should end by pointing at the blueprint's
   "real" version.)
3. **Author notebooks in parallel**, one agent owning a disjoint set of chapters, each
   **executing every notebook top-to-bottom** (papermill/nbval) and fixing errors before
   returning. Mirror the book's drafting method.
4. **Verify in CI** — notebooks run on a schedule against mock modes (no API spend) and,
   gated, against live APIs. The capstone gets its own `docker compose up` smoke test.
5. **Audit from multiple angles** — runs-clean, matches-book, costs-bounded, no-secrets,
   teaches-not-just-shows. Fix seams.

### Phase 3 — Republish the book (master 2nd edition)
Only after the repo is built and tested: update the book to reference it, rebuild, QA, and
re-publish. The full plan and edit-point list is in
[`BOOK-INTEGRATION.md`](BOOK-INTEGRATION.md).

---

## 6. Conventions (summary)

- **Folder names:** kebab-case; chapters keep the book's `NN-slug` numbering exactly.
- **Notebook names:** `NN-MM-short-title.ipynb` where `NN` = chapter, `MM` = order within.
- **Callouts** mirror the book's emoji grammar (🧠 mental model, 🔧 build, ⚠️ pitfall,
  🎯 senior lens, 📋 checklist) so the two read as one product.
- **Every notebook** opens with a standard header cell and ends with a recap + exercises.
- Full rules + the canonical `PLAN.md` template: [`CONVENTIONS.md`](CONVENTIONS.md).

---

## 7. Definition of done for Phase 1

- [x] Every part has a folder and README; every chapter has a folder and `PLAN.md`.
- [x] `blueprints/`, `templates/`, `capstone-project/` each have a catalog + per-asset `PLAN.md`.
- [x] Standards docs (`NOTEBOOK-STANDARDS`, `CONVENTIONS`) + learner/setup docs exist.
- [x] `BOOK-INTEGRATION.md` enumerates every place the 2nd edition must change.
- [x] Repo pushed public; README clearly marks it a planning skeleton.
