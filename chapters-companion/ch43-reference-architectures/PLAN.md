# Ch 43 — Reference Architectures & Case Studies

> Companion plan · Part XI · book file `chapters/43-reference-architectures.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is a **reference/concept chapter**, and its companion is deliberately concept-light on
*new* code: the four architectures it teaches (enterprise RAG assistant, autonomous
workflow/ops agents, customer-facing copilots, batch pipelines) are already implemented as
**blueprints** elsewhere in the repo. Re-building them here would duplicate that work and tempt
readers to skip the real thing. Instead the companion adds one **concept-lab** that drives home
the chapter's actual lesson — *the ranked requirements, not the technology, chose every box* —
by letting the reader change a requirement and watch the right architecture (and its signature
pattern) fall out. The notebook's payload is its cross-links: each architecture points hard at
the blueprint that realizes it, so this chapter is the **index from "which shape?" to "study
and lift the real one."**

## Planned notebooks

### 43-01 · `43-01-requirement-driven-architecture.ipynb` — Which requirement forced which box
- **Type:** concept-lab
- **Maps to:** §43.1 (enterprise RAG), §43.2 (workflow/ops agents), §43.3 (copilots at scale),
  §43.4 (batch pipelines), §43.5 (the comparison table + the ADR-044 discipline).
- **Objective:** given a ranked requirement set, identify which of the four reference
  architectures fits, name its *hardest problem* and *signature pattern*, and point to the
  blueprint that implements it — then defend the choice the way the chapter does.
- **Prereqs:** Ch 42 (the method — this chapter is "the answers" to that method); Ch 13 (RAG),
  Ch 31/33 (durable workflows), Ch 39–40 (gateway/caching), Ch 15 (structured outputs) read.
- **Cell arc:**
  - 🧠 mental model: requirement first, box second — "if no requirement forced a box, the box
    is fashion" (§43.5 senior lens); reproduce the four-row comparison table as a small data
    structure (architecture → hardest problem, signature pattern, top risk).
  - For each architecture, a tight requirement→shape mapping cell: *permissions* made the RAG
    assistant (ACL-filtered retrieval + citations); *durability+audit* made the ops agent
    (durable engine + autonomy dial); *latency × unit-cost* made the copilot (tiered routing +
    caching); *cost-per-item* made the batch pipeline (manifest + batch APIs + sampling QA).
  - A tiny **router function** the reader runs: feed it a ranked-requirement profile, it returns
    the matching architecture + its signature pattern (pure lookup over the table — offline).
  - 🔮 *predict*: flip the top requirement of one scenario (e.g. give the RAG assistant a hard
    cost-per-item budget) and predict which architecture it becomes before the function answers.
  - A worked **autonomy-dial** cell (§43.2 senior lens): simulate per-action agreement rates and
    show the rule "promote an action to autonomous when agreement clears your threshold" — the
    most reusable pattern in the chapter, and the seed Ch 44 reuses for shadow-mode launch.
  - Cost-as-product cell (§43.3): a back-of-envelope reusing Ch 42's estimator to reproduce the
    ADR-044 logic — frontier-only ≈ \$0.55/user/mo vs a \$12 plan → tiered routing is forced.
  - ⚠️ pitfall: the enterprise-RAG breach pattern — index built with a privileged service
    account, retrieval ignores ACLs, the model summarizes the comp file (§43.1). Show "filter at
    retrieval, before any text reaches the model"; the model *cannot unsee* what retrieval hands it.
  - 🎯 senior lens: a reference architecture borrowed without recorded reasoning is cargo cult;
    with ADRs for the deltas it's defensible judgment — the deltas *are* your ADRs (§43.5).
- **Datasets/fixtures:** none — the comparison table and a few requirement profiles are in-cell
  literals; no external services.
- **APIs & cost:** none/offline — table-driven reasoning + tiny estimation; deterministic in CI.
- **You'll be able to:** match a requirement profile to the right architecture, name why each
  box exists, spot a "fashion" box, and jump straight to the blueprint that implements it.

## Feeds (cross-pillar)
- **Blueprint(s):** this chapter is primarily a **cross-link hub** — it does not author new
  blueprints; it indexes the existing ones:
  - Enterprise RAG → [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/) (ACL-aware
    retrieval, citations, faithfulness/permission-probe evals via
    [`blueprints/eval-harness/`](../../blueprints/eval-harness/)).
  - Workflow/ops agents → [`blueprints/multi-agent-supervisor/`](../../blueprints/multi-agent-supervisor/)
    + the durable-run/idempotency seams of [`blueprints/agent-loop/`](../../blueprints/agent-loop/).
  - Copilot at scale → the model gateway / tiered routing in
    [`blueprints/observability-stack/`](../../blueprints/observability-stack/) cost layer and
    the capstone gateway (Ch 39–40), with guardrails from Ch 41.
  - Batch pipelines → the structured-output + sampling-QA patterns (Ch 15) and
    [`blueprints/eval-harness/`](../../blueprints/eval-harness/) golden-set sampling.
- **Template(s):** [`templates/adr-template/`](../../templates/adr-template/) — the chapter's
  ADR-044 is the worked instance; "the deltas are your ADRs" is the template's reason to exist.
- **Capstone:** no new capstone code — the four architectures are the *case studies* that
  `capstone-project/` (an enterprise-RAG + workflow hybrid) and its `agents/`, `rag/`, `workers/`,
  gateway layers instantiate; Ch 44 then tours that instantiation.

## Dependencies
- Ch 42 (the method these are answers to — run its estimator first) · Ch 13, 22 (RAG + evals
  for the assistant) · Ch 31, 33 (durable workflows for ops agents) · Ch 39–41 (gateway,
  caching, guardrails for copilots) · Ch 15 (structured outputs for batch). Forward: Ch 44
  assembles one of these (the workflow/RAG hybrid) as the full capstone.

## Phase-2 definition of done
- [ ] 43-01 runs top-to-bottom fully offline with no errors.
- [ ] The four architectures' hardest-problem / signature-pattern / top-risk rows match §43.5's
      table exactly; the router function returns them correctly for the book's scenarios.
- [ ] The ADR-044 cost logic (≈ \$0.55/user/mo, 78% small-model match, ~70% reduction) reproduces.
- [ ] Recap + 2–4 exercises ("change one requirement; which box must change?"); every
      blueprint/template cross-link resolves on GitHub and locally.
