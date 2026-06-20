# Ch 2 — How to Use This Book

> Companion plan · Part I · book file `chapters/02-how-to-use-this-book.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
**Reference/orientation-only — no notebook, by design.** This chapter is the book's user
manual (the spine, the capstone-you-build-yourself, the competency tree, the self-assessment,
how to practice). Its companion analog is *how to use this repo alongside the book*, which is
prose and a worksheet, not runnable code — forcing a notebook here would be padding. So this
`PLAN.md` instead specifies the orientation surface the repo owes the reader and one optional
worksheet, and it carries the pedagogy guardrail forward: the companion **supports building
the capstone yourself; it must never become the skip-the-work shortcut** the chapter warns
against (§2.1 key idea, §2.5 "tutorial hell" 🎯).

## Planned notebooks
*None.* This is a reference/worksheet chapter. Rationale: §2 is method and navigation, not a
mechanism to run. The deliverables below are docs + one optional fill-in worksheet.

### Orientation deliverables (Phase 2, not notebooks)
- **Map the book's structure onto the repo.** A short section in
  [`docs/HOW-TO-USE.md`](../../../docs/HOW-TO-USE.md) that mirrors §2.1–2.2: the book's spine
  and capstone ↔ the repo's four pillars (`learn/` labs · `blueprints/` reference ·
  `templates/` scaffolds · `capstone/` answer key). States plainly: **you still build the
  capstone yourself; `capstone/` is to check/compare/unblock, not to clone.**
- **Reading paths.** Translate the chapter's "read straight through vs jump to your gaps" into
  concrete repo routes (a per-part `learn/.../README.md` trail; which notebooks are
  prerequisites for which).
- **Setup pointer.** Tie §2.4 (Python 3.12+, Node, Docker, a model key, AWS later) to
  [`docs/SETUP.md`](../../../docs/SETUP.md) and `.env.example`, echoing the chapter's "don't
  install everything on day one" ⚠️ — add tooling when the chapter that needs it arrives.
- **The `MOCK` covenant.** Explain, once and centrally, the `COMPANION_MOCK` switch
  (offline/free default vs live API) so every later notebook can assume the reader has read it
  here. This operationalizes §2.5 "type the code; don't paste it" — the labs are for typing
  and predicting, not pasting.

### (Optional) 02-01 · `02-01-self-assessment.ipynb` — Competency-tree self-assessment worksheet
- **Type:** worksheet
- **Maps to:** §2.2 (the competency tree), §2.3 (find your gaps self-assessment), §2.5 (how to
  practice deliberately)
- **Objective:** locate yourself on the ten competency branches and generate a personal
  reading/lab plan that points at the right Parts and notebooks.
- **Prereqs:** none.
- **Cell arc:**
  - 🧠 the competency tree (the chapter's ten branches: Foundations · Model · Agents · Quality
    · Backend · Cloud · Frontend · Production · Frontiers · Career), as one figure.
  - Fill-in cells: rate each branch *solid / shaky / new* (a tiny dict or markdown table).
  - A cell that turns the ratings into a suggested route — for each *shaky/new* branch, print
    the matching Part(s) and the `learn/` folders to work fully (do every 🔧 Build); for
    *solid* branches, "skim for the senior/architect lenses."
  - 🔮 *predict* your weakest branch before scoring, then compare to what the table says.
  - A "revisit me" cell to re-score every few parts (§2.3 — watching "new" → "solid").
  - 🎯 senior lens: the §2.5 "tutorial hell" warning — always keep a project of *your own*
    moving alongside the capstone; the worksheet exists to push you to build, not to consume.
- **Datasets/fixtures:** none (reader's own ratings; no external data).
- **APIs & cost:** none — pure local worksheet, fully offline.
- **You'll be able to:** produce a personalized, branch-by-branch plan for working the book +
  repo, and a habit for re-checking progress.

## Feeds (cross-pillar)
- **Blueprint(s):** —
- **Template(s):** —
- **Capstone:** — (orientation only; reinforces the "build the capstone yourself, then compare
  against `capstone/`" framing the whole repo depends on).

## Dependencies
- None. This chapter's deliverables are mostly cross-cutting docs
  ([`docs/HOW-TO-USE.md`](../../../docs/HOW-TO-USE.md), [`docs/SETUP.md`](../../../docs/SETUP.md));
  keep them consistent with the canonical standards in
  [`docs/NOTEBOOK-STANDARDS.md`](../../../docs/NOTEBOOK-STANDARDS.md) and
  [`docs/CONVENTIONS.md`](../../../docs/CONVENTIONS.md).

## Phase-2 definition of done
- [ ] `docs/HOW-TO-USE.md` covers the book↔repo map, reading paths, the setup pointer, and the
      `MOCK` covenant — and explicitly states the capstone is build-it-yourself / compare-only.
- [ ] If the optional worksheet ships: runs fully offline, has fill-in cells + the
      rating→route logic, and carries the "tutorial hell / build your own project" senior lens.
- [ ] Terminology (the ten branches, *solid/shaky/new*, the spine + capstone) matches §2 exactly.
- [ ] No asset here tempts the reader to skip building the capstone (pedagogy guardrail).
