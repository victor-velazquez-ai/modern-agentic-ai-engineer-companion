# Ch 51 — From Senior to Architect & Tech Lead

> Companion plan · Part XIII · book file `chapters/51-senior-to-architect.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter is the architect transition — systems/second-order thinking, multiplying others,
and *driving decisions through documents and rooms*. Its companion is **one worksheet** that
makes the reader run the chapter's decision-driving loop on a real decision: frame an RFC,
pre-wire stakeholders, force an explicit decision, and record an ADR. There is **no notebook
by design** — the skill is judgment and communication, not code.

> **Why a worksheet, not a notebook (per REPO-PLAN §4 + the pedagogy guardrail):** second-order
> reasoning, the multiplier mindset, and RFC→ADR decision-driving are leadership artifacts that
> are *written and socialized*, not executed. A runnable cell can't teach "pre-align before the
> meeting." A worksheet that produces a real RFC and ADR — cross-linked to the actual templates
> the reader will reuse at work — is the right asset.

## Planned worksheets

### 51-01 · `51-01-rfc-adr-practice-worksheet.ipynb` — Drive one decision, end to end
- **Type:** worksheet  *(markdown prompts + fill-in cells; no executable code)*
- **Maps to:** book §51.1 (systems, trade-offs, second-order effects), §51.3 (driving
  decisions: RFCs, ADRs, stakeholder alignment), §51.4 (altitude switching / lead with the
  conclusion) — closes on the §51 checklist.
- **Objective:** take one real decision you face and carry it through the chapter's loop —
  RFC with honest options → pre-wiring plan → named decision-maker + date → recorded ADR —
  while practicing second-order analysis and three-altitude framing.
- **Prereqs:** book Ch 51 read; **Ch 27** (the ADR/RFC/C4 fundamentals these reuse). No tooling.
- **Cell arc:**
  - 🧠 player → *game designer*: pick a recent or pending change and trace its **second-order
    effects** — on other systems *and* on people's behavior/incentives (the §51.1 prompts:
    "what will every player naturally do?").
  - Multiplier check: fill in the "two-week vacation" test — does team velocity/decision
    quality hold without you? Name one problem you'll *delegate as an outcome* instead of
    solving solo (the §51.2 hero-engineer trap).
  - 🔧 *write* a real RFC in a markdown cell — problem, forces, two or three honest options
    with trade-offs, and a recommendation — using the book's structure (lifts into
    `templates/system-design-doc/`).
  - Pre-wiring plan: list the key stakeholders, the objection each will raise, and the
    one-on-one order to walk the doc *before* the group meeting ("decisions are made in the
    hallway; meetings ratify them").
  - 🔮 *predict* where this proposal would die of a **slow no**, then assign a decision-maker,
    a decision date, and the default-if-no-decision to prevent it.
  - 🔧 *record* the outcome as an ADR (decision, rejected options, revisit conditions) — lifts
    into `templates/adr-template/`.
  - Altitude drill: write the *same* decision three ways — one-sentence business outcome (exec),
    boundary-and-trade-off (fellow leads), mechanism (engineers) — and lead each with the
    conclusion (§51.4).
  - ⚠️ pitfall: answering an exec's risk question with pipeline internals — "context
    engineering for humans" failure; the drill makes you route the message to the room.
  - 📋 self-audit against the §51 checklist (second-order effects traced? someone grown via a
    handed-off problem? quality holds when absent? biggest decision in a pre-wired RFC? named
    decision-maker + date? one-sentence exec value?).
- **Datasets/fixtures:** none — a decision from the reader's own work (or the capstone's
  modular-monolith-vs-microservices choice) is the subject; output is an RFC + an ADR.
- **APIs & cost:** none/offline — writing and socializing artifacts only; no model calls.
- **You'll be able to:** drive a decision the way an architect does — framed, pre-wired, forced
  to an explicit call, recorded — and explain it at whichever altitude the room needs.

## Feeds (cross-pillar)
- **Blueprint(s):** — (produces leadership documents, not a runnable module; informs how every
  blueprint's decisions get recorded and reviewed).
- **Template(s):** practice consumer of the two architecture templates, cross-linked from Ch 27:
  [`templates/adr-template/`](../../templates/adr-template/) (the recorded decision) and
  [`templates/system-design-doc/`](../../templates/system-design-doc/) (the RFC/options +
  trade-off scaffold). This chapter supplies *leadership-context* example fills for both.
- **Capstone:** no code — but the RFC/ADR can target a real `capstone-project/` decision (Appendix C),
  extending the founding ADR produced in Ch 27.

## Dependencies
- **Ch 27** (ADRs, RFCs, C4, trade-off method) is the hard prerequisite — this chapter is those
  tools used as *leadership* instruments. Pairs with Ch 50 (multiplier work is next-level scope)
  and feeds Ch 54's §54.4 "lead one initiative" milestone.

## Phase-2 definition of done
- [ ] Worksheet renders top-to-bottom in `MOCK=1` (here: fully offline) with no errors; no
      executable code required.
- [ ] The RFC and ADR structures, the second-order-effects framing, and the altitude-switching
      guidance match the book's §51 (and Ch 27's ADR-014) terminology exactly.
- [ ] Outputs lift cleanly into `templates/adr-template/` and `templates/system-design-doc/`;
      ends with the §51 checklist as a self-audit plus 2–3 exercises.
- [ ] Reference/worksheet-only by design — no live APIs, no secrets, no service to run.
