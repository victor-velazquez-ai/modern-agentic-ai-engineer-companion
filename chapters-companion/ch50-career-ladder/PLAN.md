# Ch 50 — The Agentic AI Career Ladder

> Companion plan · Part XIII · book file `chapters/50-career-ladder.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Part XIII is **career, not code** — the chapter's value (the ladder, the skill/impact matrix,
proof of work) is realized by *deciding and recording where you stand*, not by running cells.
So this chapter ships **one worksheet**: a self-assessment that places the reader on the
ladder, a skill-impact matrix that surfaces hidden-gem vs. promotion-track work, and a
portfolio plan that turns the book's capstone into checkable proof. There is **no notebook by
design** — see below.

> **Why a worksheet, not a notebook (per REPO-PLAN §4 + the pedagogy guardrail):** "what level
> am I at, what next-level work can I claim, is my impact legible" cannot be executed or
> learned from code. A forced notebook here would teach nothing the prose doesn't; a worksheet
> that makes the reader *commit answers in writing* is the asset that matches §50.2's "ask your
> manager in writing" mechanism. Reflection beats a runnable cell for this material.

## Planned worksheets

### 50-01 · `50-01-ladder-and-portfolio-worksheet.ipynb` — Place yourself, then plan the proof
- **Type:** worksheet  *(markdown prompts + fill-in cells; no executable code)*
- **Maps to:** book §50.1 (the ladder as scope of ownership), §50.2 (the skill/impact matrix),
  §50.3 (portfolio & proof of work) — closes on the §50 checklist as a self-audit.
- **Objective:** state your current level's scope and the next level's in one sentence each,
  locate yourself on the skill/impact matrix, and produce a concrete portfolio plan built from
  the capstone you already have.
- **Prereqs:** book Ch 50 read; ideally the capstone work from Ch 12–44 underway (it *is* the
  portfolio). No tooling.
- **Cell arc:**
  - 🧠 the ladder as *scope of ownership*, not years/tech — fill in your current and next level
    in one sentence each (the §50.1 table as a self-locator).
  - Skill/impact matrix: rate recent work on both axes; honestly flag any "hidden gem"
    (high-skill / low-visibility) work — the chapter's named failure mode.
  - 🔮 *predict* which of your last three months of impact a promotion committee could actually
    see — and from *what artifact* — before writing the answer; most readers find the gap.
  - Next-level-scope prompt: name one piece of next-level work you could take on now, and the
    exact sentence you'd send your manager in writing (§50.2 mechanism).
  - Portfolio plan: convert the capstone into the four proof artifacts the chapter prizes —
    one finished+operated system, an eval harness with real numbers, a trace/post-mortem
    write-up, and ADRs explaining the *why*.
  - ⚠️ pitfall: "my work should speak for itself" — the chapter's most-expensive belief; the
    worksheet forces a visibility plan so impact doesn't go unwitnessed.
  - 🎯 senior lens: use the matrix *in reverse* — list one teammate whose hidden-gem work you
    will make visible this quarter.
  - 📋 self-audit against the book's §50 checklist (level scoped? next-level work claimed?
    impact legible? one operated system? eval numbers attached? last big decision recorded?).
- **Datasets/fixtures:** none — the reader's own career and capstone are the subject; output is
  prose the reader keeps.
- **APIs & cost:** none/offline — reflection only; no model calls, no secrets.
- **You'll be able to:** name your level and next-level scope precisely, see where your impact
  is invisible, and walk away with a portfolio plan whose artifacts double as promotion proof.

## Feeds (cross-pillar)
- **Blueprint(s):** — (career reflection produces a plan, not a runnable module).
- **Template(s):** the portfolio plan's "record the why" step seeds
  [`templates/adr-template/`](../../templates/adr-template/) usage; eval-harness proof points
  at the eval-harness blueprint/template the reader will have built (Part VI).
- **Capstone:** no new code — but this worksheet *reframes* `capstone-project/` (Appendix C) as the
  reader's portfolio: finish it to *operated*, attach eval numbers, write the ADRs.

## Dependencies
- Conceptually depends on the capstone existing (Ch 12–44) as the portfolio object. Feeds
  Ch 52 (interviews: the portfolio is leveling evidence) and Ch 54 (the §54.4 24-month roadmap
  opens by consolidating exactly this artifact).

## Phase-2 definition of done
- [ ] Worksheet renders top-to-bottom in `MOCK=1` (here: fully offline) with no errors; no code
      cells to execute beyond optional markdown rendering.
- [ ] The ladder levels, the skill/impact matrix cells, and the proof-of-work artifact list
      match the book's §50 terminology exactly.
- [ ] Ends with the §50 checklist as a self-audit plus 2–3 reflection exercises; nothing is
      left as a runnable-but-unteaching cell.
- [ ] Reference/worksheet-only by design — no live APIs, no secrets, no service to run.
