# Ch 44 — Capstone: End-to-End Production System

> Companion plan · Part XI · book file `chapters/44-capstone-end-to-end.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is **the** capstone integration chapter — the assembly point where every layer the book
built clicks together. Its companion is **not a new build** (that would undercut the book's
core promise); it is a guided **walkthrough that tours the finished `capstone/`** and a
**production-readiness pass** that runs the book's master checklist against it. Framed per the
pedagogy guardrail throughout: *you build yours first from the 🔧 Build sections, then use this
tour to compare, check, and unblock.* The notebooks point hard at `capstone/` and its
`checkpoints/` — the tour shows the assembled system following one request through all four
planes, then hardens it (evals, observability, guardrails, cost) and rehearses launch and
agent-version rollout, exactly as §44 walks it.

## Planned notebooks

### 44-01 · `44-01-capstone-tour-one-request.ipynb` — One request through every layer
- **Type:** walkthrough  *(a tour of the assembled `capstone/`, not a from-scratch build)*
- **Maps to:** §44.1 (bringing all layers together — the single end-to-end trace; the
  layer-by-layer table; the AWS deployment diagram).
- **Objective:** follow one real request ("summarize last week's feedback and file the top
  three issues") through `capstone/` — frontend → thin FastAPI intake → queue → Celery worker
  → agent plan/retrieve/tool-via-MCP-with-approval/checkpoint → gateway → SSE stream → trace —
  and name which `capstone/` directory and which book chapter owns each hop.
- **Prereqs:** the whole book; ideally your own capstone attempt + Ch 12–41 notebooks. This
  notebook *reads and traces* the reference `capstone/`; it assumes it's been built (or uses
  `checkpoints/`).
- **Cell arc:**
  - 🧠 mental model: the four planes from Ch 3 stayed the load-bearing walls from first diagram
    to last — every chapter furnished a plane; nothing replaced the frame (§44.1).
  - Map cell: render the §44.1 layer table (Agent core → Knowledge → Orchestration → Quality →
    Backend → Architecture → Data → Async → Cloud → Frontend → LLMOps) onto the `capstone/`
    directory tree, each row linking the dir + the chapters that built it.
  - Trace the request hop by hop in **mock mode**: intake persists a run row + enqueues and
    returns a stream handle (thin intake, per Ch 42); 🔮 *predict* what intake does *not* do
    (no model calls — so it can't be taken down) before revealing it.
  - Worker hop: agent plans → retrieves from pgvector → calls the ticketing tool through MCP,
    *gated by an approval* (filing issues is a side effect, Ch 20) → checkpoints each step (Ch 14).
  - Gateway hop: each model call routed, budget-checked, breaker-protected (Ch 39); the SSE
    stream renders steps, citations, and the approval card (Ch 38).
  - Exhaust hop: the trace (every span, token count, cost) lands in observability (Ch 23), and
    a wrong retrieval is shown being promoted into the eval set tomorrow (Ch 22) — the flywheel.
  - ⚠️ pitfall: mistaking "the model" for "the system" (Ch 3 callback) — point at how many hops
    in this trace are *not* the model, where most failures actually live.
  - 🎯 senior lens: a good early mental model means three hundred pages later the map still
    matches the territory — the payoff of Ch 3's four planes (§44.1 mental-model callout).
  - Closes by pointing at `capstone/README.md` (Appendix C mapping) and the matching
    `checkpoints/` so a reader can diff their own assembly against this known-good state.
- **Datasets/fixtures:** tiny canned trace + 2–3 in-memory "feedback" docs so the tour runs
  with no services; the *real* request path lives in `capstone/`, which this notebook references.
- **APIs & cost:** mockable — `MOCK=1` replays a canned end-to-end trace (free, deterministic);
  `MOCK=0` (opt-in, ⚠️ flagged) drives the actual local `capstone/` via `docker compose`.
- **You'll be able to:** narrate the entire capstone as one request across four planes, and
  locate any layer in both the book and the `capstone/` tree.

### 44-02 · `44-02-production-readiness-pass.ipynb` — Harden it, then run the master checklist
- **Type:** worksheet  *(the production-readiness pass — checklist as runnable gates where it can be)*
- **Maps to:** §44.2 (versioning & rolling out agents — the prompt+tool+model triple, canary on
  *quality*, A/B, shadow mode, two rollback levers), §44.3 (hardening: evals, observability,
  guardrails, cost), §44.4 (launch/operate/iterate), §44.5 (the full production-readiness checklist).
- **Objective:** take `capstone/` (or your own system) through the book's master checklist —
  confirming the hardening is wired *in* (not bolted on) — and leave with every box owned,
  checked, or flagged, plus a rehearsed agent-version rollback.
- **Prereqs:** 44-01.
- **Cell arc:**
  - 🧠 mental model: hardening is one posture — *assume failure, measure quality, bound the blast
    radius* — breakers assume provider failure, evals assume your regressions, guardrails assume
    hostile input, caps assume runaway spend, kill switches assume you'll be wrong (§44.3 key idea).
  - Agent-as-artifact cell: show the **prompt + tool + model triple** pinned as one versioned
    unit, recorded per run (§44.2); 🔮 *predict* what breaks if a provider silently repoints a
    model alias underneath you — then see why the triple, not the prompt file, is the rollout unit.
  - Rollout simulation (offline): canary watching *online eval scores + cost*, not just errors;
    a quality drop on 5% caught before 100%; contrast a 500-only canary that's blind to it.
  - Shadow-mode cell: run a "new" agent alongside the incumbent on replayed traffic, log what it
    *would* have done, serve the incumbent — banking agreement-rate (the Ch 43 autonomy dial at a
    version bump).
  - **Two rollback levers** made concrete: code rollback (redeploy previous image) vs
    agent-version rollback (repin the triple, config-only, instant, no deploy); ⚠️ pitfall:
    confusing them during a 2 a.m. "it's hallucinating refunds" incident.
  - Hardening checks as runnable assertions where possible: an eval gate that *fails* a merge on
    a dropped metric (Ch 22); a trace asserting per-tenant token/cost accounting exists (Ch 23);
    a structural-guardrail probe (least-privilege tool scope / tenant isolation in the data
    layer, not the prompt — Ch 41); a budget cap tripping at 50/80/100% with a per-feature kill
    switch (Ch 39–40).
  - ⚠️ pitfall: hardening *sequentially* ("ship first, add evals/guardrails next sprint") — next
    sprint never comes, traffic does (§44.3). The pass enforces in-build hardening.
  - 📋 the **full production-readiness checklist** (§44.5) as the closing artifact: walk all
    seven sections — Architecture & design, Reliability & scale, Data, Security & safety,
    Quality (evals & observability), Cost, Operations & launch — marking each box owned/checked
    against `capstone/` (or your system) with the chapter reference.
  - 🎯 senior lens: after launch the scarce resource is *trust in the iteration loop* — make the
    disciplined path the easy path (harness in CI, flags in place, dashboards one click away);
    process you must remember erodes, so build it into the rails (§44.4).
- **Datasets/fixtures:** tiny canned eval set + a replayed traffic slice for the canary/shadow
  simulations; the real gates live in `capstone/evals/` and the gateway, which this references.
- **APIs & cost:** mockable — simulations and checklist run offline in `MOCK=1`; the live gates
  ride on `capstone/`'s own CI/`docker compose` smoke test (opt-in, ⚠️ flagged).
- **You'll be able to:** run the master readiness checklist against any agentic system, wire the
  four hardening postures in *while* building, and rehearse an agent-version rollback separately
  from a code rollback.

## Feeds (cross-pillar)
- **Blueprint(s):** this chapter *consumes and assembles* the blueprints rather than adding one —
  it is the place [`blueprints/agent-loop/`](../../../blueprints/agent-loop/),
  [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/),
  [`blueprints/multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/),
  [`blueprints/eval-harness/`](../../../blueprints/eval-harness/), and
  [`blueprints/observability-stack/`](../../../blueprints/observability-stack/) all show up
  together inside one running system.
- **Template(s):** [`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/)
  (the thin-intake API the capstone realizes) and the master-checklist instance contributed to
  [`templates/production-readiness-checklist/`](../../../templates/production-readiness-checklist/)
  (Appendix F); cross-links to [`templates/system-design-doc/`](../../../templates/system-design-doc/)
  (Ch 42) and [`templates/adr-template/`](../../../templates/adr-template/).
- **Capstone:** **the whole `capstone/`** — this chapter is its guided tour. 44-01 walks
  `capstone/{app,workers,agents,rag,memory,mcp,evals,infra,web}/`; 44-02 runs the readiness pass
  against `capstone/evals/` + the gateway + guardrails, and exercises the
  [`capstone/checkpoints/`](../../../capstone/checkpoints/) scheme ("diff yours against
  known-good") and the AWS deploy (`capstone/infra/`, Ch 33/36).

## Dependencies
- Effectively the entire book, but especially: Ch 3 (four planes), Ch 12–20 (agent core,
  orchestration, MCP, approval gates), Ch 22–23 (evals + observability), Ch 25–31 (backend,
  data, workers), Ch 33–36 (cloud/IaC), Ch 38 (frontend), Ch 39–41 (gateway, cost, security),
  Ch 42 (the method + estimate this readiness pass references), Ch 43 (autonomy dial / shadow
  mode). The capstone and its checkpoints must exist (built in Phase 2) before these run live.

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (canned trace / replayed traffic) with no
      errors; the live (`MOCK=0`) path drives `capstone/` via `docker compose` and is opt-in.
- [ ] 44-01's layer→directory→chapter map matches §44.1's table and the actual `capstone/` tree.
- [ ] 44-02 reproduces every section of the §44.5 master checklist, the prompt+tool+model triple
      framing, and the *two distinct rollback levers*; eval-gate/cost-cap assertions actually fire.
- [ ] Both notebooks frame the capstone as **"build yours first, then compare"** and end by
      pointing at `capstone/` + the matching `checkpoints/`; all cross-links resolve.
