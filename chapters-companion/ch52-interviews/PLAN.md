# Ch 52 — Interviews & Demonstrating Mastery

> Companion plan · Part XIII · book file `chapters/52-interviews.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The chapter's payload is a *performable* skill: run the five-phase AI system-design framework
aloud, reach evaluation-and-operations unprompted, and tell level-appropriate behavioral
stories. The companion makes that drillable with **one worksheet**: system-design drill cards
on real agent-product prompts, each paired with a **self-scoring rubric**, plus a behavioral
story-bank and a leveling/negotiation prep sheet. There is **no notebook by design** —
interview performance is rehearsed and self-scored, not executed.

> **Why a worksheet, not a notebook (per REPO-PLAN §4 + the pedagogy guardrail):** the asset
> that improves interview performance is *repetition against a rubric*, not running code. A
> worksheet with drill prompts + self-scoring rubrics gives the reps and the feedback signal a
> notebook can't. (The chapter's coding-round prep is already covered by Part II's runnable
> notebooks; we point there rather than duplicate.)

## Planned worksheets

### 52-01 · `52-01-system-design-drills-and-rubrics.ipynb` — Drill the framework, score yourself
- **Type:** worksheet  *(prompts + self-scoring rubric cells; no executable code)*
- **Maps to:** book §52.1 (the five-phase AI system-design framework + worked example), §52.2
  (coding/ML/behavioral rounds), §52.3 (negotiation & leveling) — closes on the §52 checklist.
- **Objective:** run the five-phase framework cold on several agent-product prompts, self-score
  each against a rubric that rewards trade-off narration and *unprompted* eval/ops, build a
  behavioral story-bank, and prepare a leveling+negotiation sheet.
- **Prereqs:** book Ch 52 read; **Ch 42** (the system-design method these drills perform);
  **Ch 27** (-ilities ranking, used in Phase 2 of the framework). No tooling.
- **Cell arc:**
  - 🧠 the five phases (Clarify → Rank the -ilities → Shape → Deep-dive → Evaluate & operate) as
    "the book's method performed aloud"; study the chapter's customer-support worked example.
  - Drill cards: 3+ fresh prompts (e.g. "meeting-notes agent," "code-review bot," "research
    assistant over internal docs") — fill in all five phases for each in a structured cell.
  - 🔮 *predict-then-check* per drill: before scoring, predict which phase you'll be weakest on;
    most readers discover they stop at "Shape" and never reach Evaluate & operate unprompted.
  - 📋 self-scoring rubric per drill: did you clarify autonomy ("act vs only say")? rank and
    *sacrifice* -ilities? narrate *why* each boundary falls where it does? deep-dive failure
    modes / prompt injection / cost — not happy paths? reach evals → shadow→assist→bounded
    rollout and cost/drift dashboards **without being asked**? (Phase 5 is the differentiator.)
  - ⚠️ pitfall: silently making choices the interviewer silently disagrees with — the rubric
    scores *spoken* trade-off reasoning, which converts even a "wrong" choice into senior signal.
  - Behavioral story-bank: draft six to eight true stories (hard call, conflict, failure +
    what it changed, a time you multiplied someone) with situation / *your specific actions* /
    measured result — told at the highest level that is true.
  - ⚠️ pitfall: "we" is a level-killer — rewrite one story from "we migrated…" to your precise
    part ("I wrote the RFC, aligned three teams, built the eval gate").
  - Leveling & negotiation sheet: target level + its scope; researched market range for *this*
    company (not stale book numbers); the down-level-trap questions to ask in writing; at least
    one parallel process to create alternatives.
  - 🎯 senior lens: you're generating *evidence the interviewer can advocate with* — every cell
    here is in service of that, not of passing a quiz.
- **Datasets/fixtures:** none — prompts and the reader's own history are the material; output is
  filled drills, scores, a story-bank, and a prep sheet the reader keeps.
- **APIs & cost:** none/offline — rehearsal and self-scoring only; no model calls, no secrets.
  (Live market-comp numbers are researched by the reader, not hardcoded — the chapter is
  explicit that any book's numbers go stale.)
- **You'll be able to:** run the five-phase framework cold and reach evaluation/operations
  unprompted, tell leveled behavioral stories in *your* voice, and walk into leveling +
  negotiation with a researched plan and an alternative in hand.

## Feeds (cross-pillar)
- **Blueprint(s):** — (interview prep produces rehearsal artifacts, not a runnable module).
- **Template(s):** the system-design drills practice the same scaffold as
  [`templates/system-design-doc/`](../../templates/system-design-doc/) (C4 + -ilities +
  trade-offs), making interview reps and on-the-job design docs one muscle.
- **Capstone:** no code — but the portfolio system from `capstone-project/` (Appendix C) is named in
  §52.3 as leveling evidence when an offer comes in below the interviewed level.

## Dependencies
- **Ch 42** (system-design method) and **Ch 27** (-ilities, ADR/RFC) are the technical
  prerequisites the drills perform; **Ch 50** supplies the portfolio used as leveling evidence.
  Part II notebooks cover the coding-round prep this worksheet deliberately doesn't duplicate.

## Phase-2 definition of done
- [ ] Worksheet renders top-to-bottom in `MOCK=1` (here: fully offline) with no errors; no
      executable code required.
- [ ] The five phases, the worked-example moves, and the rubric criteria match the book's §52
      framework exactly; Phase 5 (evaluate & operate, unprompted) is weighted as the
      differentiator the chapter says it is.
- [ ] Includes self-scoring rubrics, a 6–8 story behavioral bank, and a leveling/negotiation
      sheet; ends with the §52 checklist as a self-audit plus 2–3 exercises.
- [ ] Reference/worksheet-only by design — no live APIs, no hardcoded comp numbers, no secrets.
