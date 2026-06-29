# Part XI — Architecting & Designing Systems at Scale (Ch 42–44)

> 📓 Companion to **Modern Agentic AI Engineer** · Part XI · `learn/part-11-architecting-at-scale/`
> Status: 📋 planned (Phase 1) — these folders hold `PLAN.md` files; notebooks land in Phase 2.

## What this part adds to the book

This is the **senior/architect capstone of skills** — the part where every piece the book
built (agents and retrieval, backends and queues, clouds and pipelines, evals and guardrails)
stops being a pile of components and becomes a *system you can defend*. It is, by the book's own
framing, **where the career-defining value lives**: a model can implement any component you
specify, but deciding *which* components this business needs, under these constraints, with the
trade-offs made explicit, is the judgment that stays human as AI writes more of the code. These
three chapters are the part you reach for in roadmap meetings, design reviews, and interviews.

Part XI is the convergence point of two earlier spines:

- It **brings Ch 27's architectural judgment together with Ch 29's distributed-systems reality.**
  Ch 27 taught the trade-off discipline (rank the -ilities, weigh candidates, record ADRs);
  Ch 29 taught the failure laws (timeouts, retries, idempotency, back-pressure). Ch 42's method
  fuses them and adds the *AI-specific physics* — tokens, latency, quality, and cost — that turn
  a generic system-design method into one for agentic systems.
- It is **where the capstone is finally assembled and hardened.** Everything since Ch 12 has been
  furnishing one of Ch 3's four planes; Ch 44 is the assembly point, and it tours the finished
  `capstone-project/` rather than building a new one — honoring the book's promise that *you* build yours
  first, then compare against the reference.

The companion honors the part's nature: it is **deciding-heavy, not code-heavy.** Ch 42 ships a
genuinely runnable, fully offline **estimation lab** (numbers kill bad designs cheaply) plus a
**system-design worksheet**; Ch 43 is a **concept/reference** chapter that cross-links to the
blueprints which already implement its four architectures (no duplicate builds); Ch 44 is a
**guided tour + production-readiness pass** over `capstone-project/`. Everything runs **offline and free**
by default (`MOCK=1`), with any live path opt-in and clearly flagged.

## Chapters in this part

| Ch | Title | Companion emphasis | Notebooks | Plan |
|---|---|---|---|---|
| 42 | System Design for AI: A Method | Concept + worksheet — a runnable **back-of-envelope estimator** (🔧 Build §42.7: traffic/tokens/\$/storage, fully offline) and a seven-step **system-design worksheet** (requirements→constraints→architecture, reliability patterns, the data flywheel) → `system-design-doc`, `adr-template`. | 2 | [PLAN](42-system-design-for-ai/PLAN.md) |
| 43 | Reference Architectures & Case Studies | Concept/reference — one **requirement-driven** concept-lab over the four architectures (enterprise RAG · workflow/ops agents · copilots · batch pipelines): which requirement forced which box, the autonomy dial, cost-as-product — then cross-link to the blueprint that implements each. Light new code by design. | 1 | [PLAN](43-reference-architectures/PLAN.md) |
| 44 | Capstone: End-to-End Production System | The capstone integration chapter — a **guided tour of the assembled `capstone-project/`** (one request across all four planes) + a **production-readiness pass** (agent versioning/rollout, hardening, the master checklist). *Build yours first, then compare.* | 2 | [PLAN](44-capstone-end-to-end/PLAN.md) |

## Feeds at a glance

- **Blueprints:** Part XI authors **no new blueprints** — it *selects among* and *assembles* the
  existing ones. Ch 43 is a cross-link hub into
  [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/),
  [`blueprints/multi-agent-supervisor/`](../../blueprints/multi-agent-supervisor/),
  [`blueprints/eval-harness/`](../../blueprints/eval-harness/), and
  [`blueprints/observability-stack/`](../../blueprints/observability-stack/); Ch 44 is where they
  all appear together inside one running system (with
  [`blueprints/agent-loop/`](../../blueprints/agent-loop/)).
- **Templates:** Ch 42 → [`templates/system-design-doc/`](../../templates/system-design-doc/) and
  [`templates/adr-template/`](../../templates/adr-template/) (the design doc + ADR it emits);
  Ch 43 → `adr-template` (its deltas-are-ADRs discipline); Ch 44 → the master
  [`templates/production-readiness-checklist/`](../../templates/production-readiness-checklist/)
  (Appendix F) and [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/).
- **Capstone:** Ch 42 is *the method `capstone-project/` was designed by*; Ch 44 is **the guided tour of
  `capstone-project/`** end to end and runs the readiness pass against
  [`capstone-project/`](../../capstone-project/) and its [`checkpoints/`](../../capstone-project/checkpoints/).

## Suggested path

Run the chapters **in order — they compound.** Start with **Ch 42**: its estimation lab is the
recommended entry point and the single most transferable hour in the part — you reuse the
estimator in both later chapters. Then **Ch 43** applies that method to the four architectures you
will actually be asked to build, teaching you to read requirements→shape (and to spot a "fashion"
box). Finally **Ch 44** assembles one of those shapes as the full capstone and hardens it with the
master checklist — the book's single operational artifact.

New to the repo? Make sure Part I's
[`03-mental-model`](../part-01-landscape-and-mindset/03-mental-model/PLAN.md) (the four planes)
and the heavy backend/architecture work of **Part VII** (esp. Ch 27 ADRs and Ch 29 distributed
systems) are behind you — Part XI is where those two threads converge.

See [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) for the full chapter→asset map and
[`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) for the `PLAN.md` template these follow.
