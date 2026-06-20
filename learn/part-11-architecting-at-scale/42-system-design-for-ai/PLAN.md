# Ch 42 — System Design for AI: A Method

> Companion plan · Part XI · book file `chapters/42-system-design-for-ai.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter is a *method*, not a mechanism, so the companion's job is to make the method
**executable** rather than handing over code. Two assets do that: a runnable **estimation
notebook** that turns the book's back-of-envelope arithmetic (§42.3) into a calculator you
change and re-read until the numbers, not your instincts, kill the bad design — and a
**system-design worksheet** that walks the seven-step method end to end on a prompt of your
own and emits a real design doc. Together they convert "I read the method" into "I ran the
method," which is the only version that transfers to a roadmap meeting or a Ch 52 interview.

## Planned notebooks

### 42-01 · `42-01-back-of-envelope-estimation.ipynb` — Traffic, tokens, dollars, storage
- **Type:** concept-lab  *(runnable, fully offline — the chapter's 🔧 Build §42.7 worked example)*
- **Maps to:** §42.3 (back-of-envelope estimation for AI workloads), and the §42.7 worked
  example whose Step 3 estimate this reproduces; touches §42.1's "numbers kill bad designs."
- **Objective:** size any agentic feature in ten minutes — peak request/call rate, tokens/day,
  \$/day and \$/task, vector and trace storage — from a handful of assumptions, and read which
  multiplier dominates the bill.
- **Prereqs:** Ch 40 (cost/latency/performance) read; Ch 30 (data layer) for the storage math.
  No prior notebook required — this is Part XI's recommended entry point.
- **Cell arc:**
  - 🧠 mental model: spend scales as users × requests × loop turns × tokens/turn × price —
    four innocent multipliers; estimate at the *token* level, never the request level (§42.3 ⚠️).
  - Encode the book's anchors as constants (a day ≈ 86,400 s; word ≈ 1.3 tokens; page ≈ 500
    tokens; 1,536-dim float32 embedding ≈ 6 KB) and a tiny `estimate(assumptions) -> report`.
  - Reproduce the chapter's 10k-DAU scenario; 🔮 *predict* the \$/day before revealing
    ≈ \$4,000/day ≈ \$0.02/request; confirm against §42.3.
  - Latency physics: at ~60 output tok/s, show 4 sequential calls ≈ 33 s → the cell concludes
    "this cannot be a blocking request–response API" (matches §42.3's latency paragraph).
  - Storage: 2M chunks × 6 KB ≈ 12 GB vectors vs traces at ~50 KB/req → ≈ 3.6 TB/year, so
    traces need tiering and vectors don't.
  - Sensitivity sweep: re-run with loop depth 4→8, or +1,000 tokens of prompt, and watch the
    \$/day jump (the §42.3 pitfall: "+1,000 tokens = +\$800/day" reproduced as output).
  - ⚠️ pitfall: counting *requests* when the cost driver is *tokens* — show both side by side.
  - 🎯 senior lens: precision is worthless; reliably within 3× is what changes a decision —
    so optimize the estimate for *speed of judgment*, not decimal places (§42.3 tip).
- **Datasets/fixtures:** none — assumptions are dict literals in the first cell; no I/O.
- **APIs & cost:** none/offline by design (pure arithmetic) — runs free and deterministic in CI.
- **You'll be able to:** estimate tokens, dollars, peak call rate, and storage for any agentic
  feature, and name the binding multiplier before writing a line of code.

### 42-02 · `42-02-run-the-method-worksheet.ipynb` — Requirements → constraints → architecture
- **Type:** worksheet
- **Maps to:** §42.1 (the seven-step method), §42.2 (clarifying requirements/SLOs), §42.4
  (reliability patterns + degradation ladder), §42.5 (statelessness/back-pressure), §42.6
  (the two data planes + flywheel), §42.8 (the reusable playbook + 📋 checklist).
- **Objective:** run the full method on a system *you* pick and leave with a populated
  design doc — ranked NFRs, an estimate (reusing 42-01), two or three weighed candidates, a
  failure/degradation table, a data plan, and at least one ADR with rejected alternatives.
- **Prereqs:** 42-01 (you'll embed its estimate here).
- **Cell arc:**
  - 🧠 mental model: an architecture is the *residue of constraints* — if many shapes look
    equally fine you haven't found the binding constraint yet (§42.1).
  - Fill-in: clarifying questions table (§42.2) for your system; force explicit non-goals.
  - Rank the NFRs, pinning the three AI-specific ones numerically — quality target, cost/task,
    safety posture — and note where parts deserve *different* SLOs (intake vs resolution).
  - Drop in 42-01's estimate for your assumptions; let the numbers eliminate options.
  - Per-dependency failure table you complete (timeout / retry / breaker / fallback) and write
    your **degradation ladder**; 🔮 *predict* which arrow is your weakest before filling it.
  - Data planes: state a freshness SLO and pick the cheapest pipeline that meets it; sketch the
    trace→eval flywheel as boxes, not an afterthought.
  - Write an ADR for your single most expensive decision, *including rejected alternatives*
    (the chapter's ADR-031 is the worked model to imitate).
  - ⚠️ pitfall: drawing boxes first and discovering requirements later — the worksheet's
    ordering structurally forbids it.
  - 🎯 senior lens: the method's output is *surfaced trade-offs*, not a diagram — if you didn't
    ask "at the expense of what?" three times, you ran the steps but skipped the method (§42.1).
  - 📋 closes by emitting the §42.8 playbook skeleton filled in for your system → drop into
    `templates/system-design-doc/`.
- **Datasets/fixtures:** none — prompts + fill-in markdown/code cells; output is your design doc.
- **APIs & cost:** none/offline — reflection and arithmetic only.
- **You'll be able to:** take a vague ask to a defensible, recorded architecture in an hour,
  using the same artifact for design docs, reviews, and interviews.

## Feeds (cross-pillar)
- **Blueprint(s):** — (no new blueprint; the method *selects among* existing ones — the
  degradation-ladder and back-pressure patterns it teaches are realized in
  [`blueprints/observability-stack/`](../../../blueprints/observability-stack/) and the
  reliability seams of [`blueprints/agent-loop/`](../../../blueprints/agent-loop/)).
- **Template(s):** [`templates/system-design-doc/`](../../../templates/system-design-doc/) —
  42-02's filled-in §42.8 playbook is the canonical instance of this template; also contributes
  the ADR shape consumed by [`templates/adr-template/`](../../../templates/adr-template/).
- **Capstone:** no capstone code, but this is the *method the whole `capstone/` was designed
  by*; 42-02's worked support-system answer matches `capstone/`'s intake/resolution split and
  is revisited as the readiness checklist in Ch 44.

## Dependencies
- Ch 27 (quality attributes, ADRs, C4 — the trade-off discipline this builds on) · Ch 29
  (the failure laws applied here on purpose) · Ch 40 (cost/latency anchors) · Ch 30 (storage
  math). Forward: Ch 43 applies the method to four named architectures; Ch 52 reuses it as the
  interview drill.

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (here: fully offline) with no errors.
- [ ] 42-01's numbers reproduce the book's §42.3 / §42.7 figures (≈ \$4,000/day, ≈ 12 GB,
      ≈ 3.6 TB/yr) and the "+1,000 tokens → +\$800/day" sensitivity result.
- [ ] 42-02 emits a complete design doc matching the §42.8 playbook and the 📋 checklist items.
- [ ] Recap + 2–4 exercises each (e.g. "halve loop depth — what happens to \$/task and p95?");
      cross-links to `templates/system-design-doc/` and `templates/adr-template/` resolve.
