# Ch 49 — The Frontier & Staying Current

> Companion plan · Part XII · book file `chapters/49-frontier-and-staying-current.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
**Reference + worksheet only — no notebook, by design.** This chapter teaches a *system for
staying current*: read papers efficiently, filter signal from hype, and track the ecosystem
without burning out. None of that is a thing you *execute in a kernel* — a notebook here would
be theatre (a fake "paper feed" or a toy RSS parser teaches nothing the chapter doesn't, and
any real source list goes stale the week it's committed). Per the repo's own rule — *if the
medium fights the artifact, name it and point at the right asset* — the honest companion is
two living documents: a **curated reference** and a lightweight **tracking-system worksheet**
the reader fills in for their own stack. Forcing a notebook here would violate the
"right asset per chapter, not a forced notebook everywhere" principle (REPO-PLAN §4).

## Planned assets (no notebooks)

### `REFERENCE.md` — a curated, deliberately small starting shelf
- **Type:** reference (markdown, maintained)
- **Maps to:** §49.1 (reading papers efficiently; the four filter questions), §49.3 (where
  agentic AI is heading — bet on *directions*)
- **Contents:**
  - The chapter's **20-minute paper-reading method** as a repeatable checklist (abstract →
    results/figures → limitations → method only if it survives) + the four filter questions
    (fair baseline? improvement survives production? code + independent repro? holds beyond one
    benchmark?).
  - The **demo-vs-distribution hype filter** as a one-line test to apply to any "X is solved" claim.
  - A *small, opinionated* seed list of source **types** (not a doomed-to-rot link dump):
    a couple of curated newsletters, provider/framework release notes for the stack *you* use,
    a few trusted practitioners — with an explicit "prune anything noisy three weeks running" rule.
  - The durable **directions** (as of early 2026): capability-per-dollar falling (architect for
    model swaps), lengthening autonomy horizons (bottleneck moves to eval/observability/
    permissions/blast-radius), agent *infrastructure* (MCP, A2A, identity/payments) as where the
    unsolved problems are, and *verification as the scarce skill*.
  - ⚠️ explicitly **version-stamped and prunable**: every concrete name is marked "as of early
    2026 — re-check," and the file says to delete rather than accumulate.

### `tracking-system.worksheet.md` — build your own pipeline (fill-in)
- **Type:** worksheet (fill-in prompts; little/no code)
- **Maps to:** §49.2 (tracking the ecosystem without burning out — choose few high-signal
  sources, batch it weekly, learn by building; 🧠 the *depreciation schedule* mental model;
  #pitfall: resume-driven adoption), the closing #checklist
- **Contents:**
  - **Sources** (fill in 2–3 trusted, high-signal; commit to pruning) — *few, not many*.
  - **Cadence**: one scheduled weekly batch slot (not an hourly feed) — name the day/time.
  - **The depreciation schedule**: sort *your* current learning topics into slow-depreciating
    fundamentals (loops, tools, memory, evals, distributed systems, security) vs fast-churning
    layers (provider APIs, framework idioms) to *look up on demand*.
  - **Spike log**: a template row for the quarterly two-hour build-to-decide spike ("is this
    real *for me*?") with a decide/adopt/drop outcome.
  - **Adoption gate**: the resume-driven-adoption guard — *adopt only when it solves a problem
    you can name, on the strength of your own spike*.
  - **Model-swap drill**: the chapter's final checklist item — "would my architecture survive a
    model swap next quarter at the cost of an afternoon?" — as a recurring self-audit.
  - A `📓` pointer back to the chapter's #checklist so the worksheet and book stay one product.

> Phase-2 note: optionally, a *single* tiny offline `worksheet.ipynb` could host the same fill-in
> prompts for readers who prefer the notebook surface — but it carries **no executable teaching
> code** and is not required. The markdown worksheet is the canonical artifact; this stays
> reference/worksheet-only either way.

## Feeds (cross-pillar)
- **Blueprint(s):** —
- **Template(s):** — (the tracking worksheet is itself a reusable personal-process template;
  it isn't a `templates/` engineering scaffold).
- **Capstone:** —

## Dependencies
- None to *run* (nothing runs). Conceptually it's the capstone of the technical material —
  it reframes every prior chapter as "fundamentals that depreciate slowly; look up the fast layer."

## Phase-2 definition of done
- [ ] `REFERENCE.md` + `tracking-system.worksheet.md` exist; **no executable notebook is required**
      and the PLAN's rationale for that is preserved.
- [ ] Paper-reading method, the four filter questions, and the demo-vs-distribution test match §49.1.
- [ ] The worksheet operationalizes §49.2 (few sources, weekly batch, build-to-decide) + the
      depreciation-schedule mental model and the closing #checklist.
- [ ] Every concrete source/trend is **version-stamped "as of early 2026"** and flagged prunable,
      so the asset ages honestly.
- [ ] Cross-links to the chapter (§49.x) and the book's checklist resolve.
