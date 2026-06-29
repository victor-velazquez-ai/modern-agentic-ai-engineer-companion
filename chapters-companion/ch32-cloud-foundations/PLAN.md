# Ch 32 — Cloud Foundations

> Companion plan · Part VIII · book file `chapters/32-cloud-foundations.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the chapter that turns "200+ intimidating cloud services" into four primitives and a
cost model — pure orientation, no provisioning. The single **concept lab** makes the mental
model *operational*: the reader classifies real services on sight (compute / storage /
network / identity), sees multi-AZ resilience as a structural choice, and watches a tiny
*offline* cost simulator show how architecture — not usage alone — drives the bill. Nothing
here touches a real cloud account; it is the map that makes Ch 33–36 legible.

## Planned notebooks

### 32-01 · `32-01-four-primitives-and-finops.ipynb` — Classify any cloud, then cost it
- **Type:** concept-lab
- **Maps to:** §32.1 (🧠 the four primitives), §32.2 (regions, AZs, shared responsibility),
  §32.3 (cost models + the FinOps mindset)
- **Objective:** classify any unfamiliar service into compute/storage/network/identity, and
  estimate the monthly cost of a small architecture — including the forgotten-resource trap —
  before ever provisioning anything.
- **Prereqs:** none for cloud; Ch 29–31 (distributed/data/workers) read, since the examples
  reuse that capstone shape.
- **Cell arc:**
  - 🧠 mental model: the four primitives as a 2×2 map; every service is a flavor or a combo.
  - A `classify(service)` drill over a list of ~15 AWS/Azure/GCP names — 🔮 *predict* the
    primitive for each, then check against a tiny local lookup table (offline, no SDK).
  - Build a pure-Python pricing toy: on-demand vs spot vs reserved as functions of hours/usage.
  - 🔮 *predict* which line item dominates a small always-on agent stack, then read the breakdown.
  - Toggle one knob (move a batch job to spot; turn off a dev box off-hours) and re-read the bill.
  - Shared-responsibility sorter: label ~8 concerns as "provider's job" vs "your job."
  - 🎯 senior lens: cost is an architecture decision (spot for Celery, scale-to-zero, multi-AZ
    only where it pays) — the FinOps habits that prevent a five-figure surprise.
  - ⚠️ pitfall: idle/forgotten resources (weekend GPU, oversized DB, egress) — model the
    runaway and show how a day-one budget alarm would have caught it.
- **Datasets/fixtures:** a tiny committed `data/services.json` (name → primitive) and a small
  `data/price-sheet.json` of illustrative, clearly-fake unit prices (not live pricing).
- **APIs & cost:** none — fully offline by design (no cloud account, no SDK, no spend).
- **You'll be able to:** place any service on the four-primitive map and sketch a defensible
  cost estimate (and a FinOps guardrail) for a small stack before you build it.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual; the cost-awareness lens reappears in Ch 40's token
  accounting and the `blueprints/observability-stack/` cost metrics).
- **Template(s):** —
- **Capstone:** no code yet; this is the FinOps + four-primitive lens the reader applies when
  reading the AWS deploy in `capstone-project/` (Appendix C). Notebook closes by mapping the capstone's
  pieces onto the four primitives, foreshadowing Ch 33.

## Dependencies
- None for cloud. Concepts from Ch 29–31 (distributed systems, data layer, workers) make the
  examples concrete but are not strictly required.

## Phase-2 definition of done
- [ ] Runs top-to-bottom fully offline (no key, no cloud account), deterministically.
- [ ] The four primitives, the shared-responsibility split, and the cost shapes (on-demand /
      spot / reserved) match the book's §32 terminology exactly.
- [ ] Ends by mapping the capstone onto the four primitives + pointing to Ch 33.
- [ ] Recap + 2–4 reflection exercises ("which primitive is service X?", "where would a bill
      quietly grow?"); no secrets, no network calls.
