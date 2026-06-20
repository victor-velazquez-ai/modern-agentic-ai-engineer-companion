# Ch 27 — Software Architecture Fundamentals

> Companion plan · Part VII · book file `chapters/27-software-architecture-fundamentals.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the chapter that separates a senior from everyone else, and the one whose value is
*rising* fastest: when models write the code, deciding *what* to build, *how* the pieces fit,
and *which trade-offs* to make is the durable human edge. That skill is built by **practice and
reflection, not by running code** — so this chapter is deliberately a **concept-lab + a
worksheet**, not a build. The reader does real trade-off analysis on the book's own capstone
decision, writes an ADR, and produces a C4 sketch — artifacts they keep using. The two
"templates" this chapter feeds (`adr-template`, `system-design-doc`) are the through-line.

> **Why mostly no code (per REPO-PLAN §4 + the pedagogy guardrail):** architectural judgment —
> ranking -ilities, drawing boundaries, recording the *why* — is exactly what can't be
> automated or learned by executing cells. A forced notebook would teach less than a worksheet
> that makes the reader *decide*. One small concept-lab keeps an -ility trade-off tangible; the
> rest is reflection.

## Planned notebooks

### 27-01 · `27-01-trade-offs-and-ilities.ipynb` — Make a quality-attribute trade-off tangible
- **Type:** concept-lab
- **Maps to:** book §27.3 (quality attributes / the "-ilities"), §27.4 (architectural styles),
  §27.6 (trade-off analysis: there is no "best", only fit)
- **Objective:** *feel* that you can't max every -ility at once by running a tiny model where
  pushing one quality attribute visibly costs another, then practice the book's 4-step
  trade-off method on a concrete choice.
- **Prereqs:** Ch 24–26 read (concrete backend context); no special tooling.
- **Cell arc:**
  - 🧠 functional requirements say what a system *does*; the -ilities say how *well* — and that
    is where architecture is decided (mirror the book's attribute table).
  - A small offline simulation of one trade-off: e.g. a request pipeline where adding
    replicas/checks improves a reliability/scalability score but raises a cost/latency score —
    plot the Pareto curve so "at the expense of what?" is *visible*, not abstract.
  - 🔮 *predict* which style (monolith / modular monolith / microservices / event-driven /
    serverless) wins for a given ranked force set *before* revealing the book's guidance; then
    compare against the §27.4 table.
  - Encode the book's 4-step method as a tiny structured exercise: name the forces (ranked) →
    generate 2–3 options → score each against the top -ilities in a small table → pick the
    more *reversible* one when close (the §27.6 tip).
  - ⚠️ pitfall: optimizing one -ility *in isolation* ("make it scalable!") with no "at the
    expense of what?" — the rookie move the simulation makes concrete.
  - 🎯 senior lens: "what's the simplest thing that meets the -ilities?" is the architect's
    *first* question; microservices are the most cargo-culted decision in the field.
- **Datasets/fixtures:** none — a synthetic scoring model defined inline (numbers, not data).
- **APIs & cost:** none/offline — pure local computation; no model calls, fully deterministic.
- **You'll be able to:** rank -ilities for a system and run the 4-step trade-off method to a
  defensible, reversible choice — with the cost of each option made explicit.

## Planned worksheets

### 27-02 · `27-02-adr-and-c4-worksheet.ipynb` — Write a real ADR + a C4 sketch
- **Type:** worksheet  *(prompts + fill-in cells; little/no executable code)*
- **Maps to:** book §27.1 (architecture = decisions expensive to change), §27.5 (coupling,
  cohesion, boundaries), §27.7 (communicating architecture: C4, ADRs, RFCs), §27.9 (the
  architecture review checklist)
- **Objective:** produce two durable artifacts — a complete ADR for an expensive decision and a
  C4 Context/Container sketch of the capstone — and self-audit them with the book's checklist.
- **Prereqs:** 27-01.
- **Cell arc:**
  - 🧠 architecture = the decisions *expensive to change*; sort a list of mixed decisions into
    "implementation (cheap, reversible)" vs "architecture (expensive, one-way door)" — the §27.1
    cost-to-reverse lens.
  - Boundaries drill: given a feature list, draw boundaries around *business capabilities*
    (orders, billing, search), not technical layers — fill-in prompt + a short rationale.
  - 🔧 *write* a full ADR in a markdown cell using the book's ADR-014 structure (Status /
    Context / Decision / Consequences) for a real choice — e.g. "modular monolith vs
    microservices for the agent platform"; lifts directly into `templates/adr-template/`.
  - C4 sketch: fill in the Context and Container levels for the capstone (who/what systems,
    which containers) in a structured text/diagram cell; note where human judgment concentrates
    (top levels) vs where code is machine-generated (bottom).
  - Optional tiny code cell: render a Mermaid/Graphviz C4-ish diagram from the sketch (the
    *only* code here, and it's optional) so the artifact is shareable.
  - 📋 self-audit against the book's §27.9 review checklist (requirements ranked? simplest?
    boundaries on capabilities? "at the expense of what?" answered? one-way doors justified?
    decisions in ADRs?).
  - 🎯 senior lens: taste, judgment, and review-at-scale are the three skills that compound as
    AI writes more code — this worksheet is reps for all three.
- **Datasets/fixtures:** none — the capstone's own structure is the subject; output is prose +
  one optional diagram.
- **APIs & cost:** none/offline — writing and (optional) local diagram rendering only.
- **You'll be able to:** write an ADR a team would accept and a C4 sketch that explains a
  system at the right altitude — and review an architecture against a real checklist.

## Feeds (cross-pillar)
- **Blueprint(s):** — (this chapter produces *judgment* and documents, not a runnable module;
  it informs how every other blueprint is structured and reviewed).
- **Template(s):** **primary contributor** to two templates —
  [`templates/adr-template/`](../../../templates/adr-template/) (from §27.7's ADR-014 shape) and
  [`templates/system-design-doc/`](../../../templates/system-design-doc/) (the C4 + trade-off +
  -ilities scaffold). The worksheet's outputs are seed examples for both. Also cross-linked from
  Ch 42 (system design) and Ch 51 (senior→architect / ADR-RFC practice).
- **Capstone:** no code — but 27-02 produces the capstone's founding ADR and C4 sketch
  (the architectural narrative behind `capstone/`, Appendix C).

## Dependencies
- Ch 24–26 (a concrete backend to reason about). Reused later by Ch 28 (application
  architecture / hexagonal), Ch 42 (system design), Ch 51 (architect track).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (here: fully offline) with no errors; the
      one optional diagram cell degrades gracefully if the renderer is absent.
- [ ] The -ilities table, the 5 styles + trade-offs, the 4-step method, and the ADR structure
      match the book's §27 terminology and the ADR-014 example exactly.
- [ ] The worksheet ends with the book's §27.9 review checklist as a self-audit, plus 2–3
      exercises; outputs lift cleanly into `templates/adr-template/` and
      `templates/system-design-doc/`.
- [ ] Reference/worksheet-first by design — no live APIs, no secrets, no service to run.
