# Part XIII — Career, Leadership & Building Your Future

> Companion to **Modern Agentic AI Engineer**, Part XIII · book chapters 50–54
> Status: 📋 planned (Phase 1)

## Companion emphasis

Part XIII is **career, not code** — and its companion is **worksheets, not notebooks.** This is
a deliberate design choice, not a gap to be filled later.

The rest of this repo earns its keep by letting you *run* ideas: a tool loop, a retriever, an
eval scorer. These five chapters teach something a cell can't execute — **judgment about your
own trajectory**: where you sit on the ladder, how to drive a decision through a room, how to
perform under interview pressure, how to build a public record, and how to choose between
climbing someone's ladder and building your own. The right asset for that is a **worksheet**:
markdown prompts and fill-in cells that make you *decide and commit in writing*, with the
book's own checklists turned into self-audits. A forced notebook here would teach less than the
prose already does — and the project's pedagogy guardrail (REPO-PLAN §4) is explicit that
completeness means the *right* asset per chapter, not a runnable cell everywhere. Chapters 50
and 53 are even called out by name there as reference/worksheet-only.

So every chapter in this part ships exactly **one `worksheet`-type asset** (an `.ipynb` of
markdown + fill-in cells, for tooling consistency with the rest of `learn/` — same header,
recap, and checklist grammar, just no code to execute). Each is **fully offline**: no API keys,
no token cost, no service to run. Two through-lines tie them together:

- **Your judgment is the asset.** The book's closing thesis — *AI writes the code; humans own
  the judgment* — is the spine of this part. Every worksheet invests in the judgment layer.
- **The capstone is your proof.** The `capstone/` you build through the book (Appendix C) is
  reframed here as your portfolio, your public flagship repo, and — at month 24 — either your
  architect-track evidence or your product's technical core.

Where these chapters touch real, reusable scaffolds, they **cross-link the templates rather
than duplicate them**: the ADR/RFC and system-design work (Ch 51, Ch 52, Ch 54) points at
[`templates/adr-template/`](../../templates/adr-template/) and
[`templates/system-design-doc/`](../../templates/system-design-doc/), the same templates Ch 27
seeds — so interview reps, on-the-job decision-driving, and founding decisions are one muscle.
Ch 52's coding-round prep deliberately defers to Part II's runnable notebooks instead of
re-deriving them.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 50 | The Agentic AI Career Ladder | Worksheet — self-assessment + skill/impact matrix + a portfolio plan that turns the capstone into checkable proof. No notebook by design. | [`50-career-ladder/PLAN.md`](50-career-ladder/PLAN.md) |
| 51 | From Senior to Architect & Tech Lead | Worksheet — drive one real decision end to end (RFC → pre-wire → explicit call → ADR) + an altitude-switching drill. Cross-links `adr-template`, `system-design-doc`. | [`51-senior-to-architect/PLAN.md`](51-senior-to-architect/PLAN.md) |
| 52 | Interviews & Demonstrating Mastery | Worksheet — five-phase system-design drills with self-scoring rubrics (cross-links Ch 42's method), a behavioral story-bank, and a leveling/negotiation sheet. | [`52-interviews/PLAN.md`](52-interviews/PLAN.md) |
| 53 | Personal Brand, Open Source & Community | Worksheet — a sustainable "building-in-public" cadence (niche, monthly artifact, one OSS tier, give-first networking) + the §53 checklists as a recurring self-audit. Reference/worksheet by design. | [`53-brand-open-source-community/PLAN.md`](53-brand-open-source-community/PLAN.md) |
| 54 | Building Products & Companies | Worksheet — the concrete, dated 24-month roadmap (§54.4) + the product-validation sequence and a moat/economics audit. The book's terminal worksheet. | [`54-products-and-companies/PLAN.md`](54-products-and-companies/PLAN.md) |

## Run order

These are **read-alongside worksheets**, not a build sequence — do each as you finish its
chapter. They compound in order, though: **50** (place yourself + plan the portfolio) →
**51** (drive decisions like an architect) → **52** (prove it under interview conditions) →
**53** (build the reputation that prices you before you walk in) → **54** (consolidate all of
it into a chosen 24-month roadmap). Ch 54's roadmap worksheet is the natural capstone of the
whole part — and of the book — because it pulls the artifacts from 50–53 into one dated plan.
