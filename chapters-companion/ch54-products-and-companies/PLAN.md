# Ch 54 — Building Products & Companies

> Companion plan · Part XIII · book file `chapters/54-products-and-companies.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The book's closing chapter: what transfers from engineer to founder, how to validate an AI
product before building it, where moats actually live in agentic AI, and — its only section
written about the reader specifically — a 24-month personal roadmap (§54.4). The companion is
**one worksheet** that turns §54.4 into a dated, committed plan, with the validation sequence
and a moat/economics audit feeding into it. There is **no notebook by design** — founding and
career direction are decided and committed to, not executed.

> **Why a worksheet, not a notebook (per REPO-PLAN §4 + the pedagogy guardrail):** "should this
> exist and will anyone pay" is judgment, and a 24-month roadmap is a commitment device — neither
> runs as code. The right capstone for the *career* part of the book is the reader filling in
> their own next two years and the validation sequence they'll run, not a synthetic notebook.

## Planned worksheets

### 54-01 · `54-01-24-month-roadmap-worksheet.ipynb` — Your next twenty-four months, committed
- **Type:** worksheet  *(markdown prompts + fill-in cells; no executable code)*
- **Maps to:** book §54.1 (engineer→founder: what transfers / what doesn't), §54.2 (validate,
  build, ship an AI product), §54.3 (moats, economics, the business of agentic AI), §54.4 (your
  personal roadmap) — closes on the §54 checklist.
- **Objective:** produce a concrete, dated 24-month roadmap across the chapter's four phases,
  and — if the founder path tempts you — pre-fill the validation sequence and a moat/economics
  audit so the plan rests on judgment, not enthusiasm.
- **Prereqs:** book Ch 54 read; the artifacts from Ch 50–53 (portfolio, scope, public cadence,
  community) are the inputs the roadmap consolidates. No tooling.
- **Cell arc:**
  - 🧠 a startup is a *search process for a repeatable business under a runway deadline*, not a
    product; and the founder's reward function is not the engineer's — name the three engineer
    habits the chapter flags as liabilities (perfection before contact, building as default
    verb, solving the interesting problem) and your personal tell for each.
  - The 24-month roadmap (the worksheet's spine — fill in dates calibrated to your start):
    - *Months 1–3 — consolidate:* capstone to **operated** (real users, traces, cost
      dashboard, ADRs written).
    - *Months 4–9 — become visibly senior:* claim next-level scope in writing (Ch 50); one
      public artifact per month in your niche (Ch 53); build the eval-first reputation.
    - *Months 10–15 — lead something:* drive one cross-team RFC→pre-wiring→decision→ADR loop
      (Ch 51), or run the Ch 52 interview playbook in parallel processes at your proven level.
    - *Months 16–24 — choose your ladder:* Path A (staff/architect role) **or** Path B (validate
      the painful workflow you keep noticing) — a real, *chosen* decision, not drift.
  - 🔮 *predict* your honest biggest uncertainty for Path B — the chapter insists it's almost
    never "can we build it" but "will they pay, and can we reach them" — then design the cheapest
    experiment that reduces it.
  - Validation sequence (Path B pre-fill): start-from-pain (a role's tedious, budgeted hours) →
    *sell before you build* (≈20 prospect conversations + a concierge/mockup + an ask with teeth:
    paid pilot or LOI) → build the *wedge* not the platform → make evaluation a *product feature*
    (the Part VI eval harness becomes the sales deck) → ship to a few, deeply.
  - ⚠️ pitfall: the demo trap at company scale — investors as the impressed audience; a
    fundraise running ahead of a product that still fails hard inputs. Note the gap between demo
    and dependable system *is* the company.
  - Moat & economics audit: rate your idea against the four durable advantages (workflow depth /
    proprietary data + feedback loops / trust + compliance + track record / distribution) and
    sketch unit economics — token cost, model routing (cheap triage + frontier for the hard 10%),
    caching, value-based pricing — modeling the *trend line*, not today's snapshot.
  - 🎯 senior lens: the book's through-thesis — *AI writes the code; humans own the judgment* —
    and that every roadmap move invests in the judgment layer, the asset no model release
    devalues. The moat *is* the engineering the book taught.
  - 📋 self-audit against the §54 checklist (one operated system; one next-level scope in
    writing; one monthly channel; one community; one RFC-to-ADR initiative; one chosen decision
    at month 24).
- **Datasets/fixtures:** none — the reader's own roadmap and (optional) product idea are the
  subject; output is a dated plan + a validation/moat audit the reader keeps.
- **APIs & cost:** none/offline — planning, validation design, and reflection only; no model
  calls, no secrets.
- **You'll be able to:** leave with a dated 24-month plan you chose deliberately, and — if you
  take Path B — a validation sequence and moat/economics audit grounded in the book's judgment
  layer rather than demo enthusiasm.

## Feeds (cross-pillar)
- **Blueprint(s):** — (a roadmap and validation plan, not a runnable module; the product it
  imagines would, in practice, be assembled from the repo's blueprints).
- **Template(s):** the moat/economics and validation thinking reuse the
  [`templates/system-design-doc/`](../../templates/system-design-doc/) trade-off discipline
  and the [`templates/adr-template/`](../../templates/adr-template/) for recording founding
  decisions (model-agnostic boundaries, routing you control).
- **Capstone:** no new code — but this worksheet is where `capstone-project/` (Appendix C), once
  *operated*, becomes either the architect-track proof or the technical core of the product;
  the §54.4 "Months 1–3: consolidate" milestone *is* finishing it.

## Dependencies
- The **capstone** (Ch 12–44) of the chapter's `cell arc` and roadmap, and **Ch 50–53**
  (portfolio, architect-track decision-driving, public reputation) supply every input the
  roadmap consolidates. This is the terminal worksheet of Part XIII and of the book.

## Phase-2 definition of done
- [ ] Worksheet renders top-to-bottom in `MOCK=1` (here: fully offline) with no errors; no
      executable code required.
- [ ] The engineer→founder transfers/liabilities, the validation sequence, the four moats +
      unit-economics levers, and the four roadmap phases match the book's §54 terminology
      exactly (the sequence is the point, not the literal dates).
- [ ] Ends with the §54 checklist as a self-audit plus 2–3 exercises; the roadmap is dated and
      consolidates the Ch 50–53 artifacts.
- [ ] Reference/worksheet-only by design — no live APIs, no secrets, no service to run.
