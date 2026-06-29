# Ch 20 — Human-in-the-Loop & Agent UX

> Companion plan · Part V · book file `chapters/20-human-in-the-loop.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter pushes back on the whole Part's drive toward autonomy: an agent that can act on
real systems can act *wrongly* on them. The notebooks make the chapter's two control axes
runnable — risk-tier gating ("how expensive to reverse?") and confidence escalation ("is the
agent probably wrong?") — and then deliver the chapter's 🔧 **Build**: wiring the risk-tier table
into the capstone's loop so a gated call **parks the run as `waiting_human`** and an approval
(arriving minutes or days later) resumes it with the decision injected as a tool result. The
through-line the chapter stresses: the gate is *architecture you already had* — checkpoints gave
pause, tool results gave a channel for human decisions.

## Planned notebooks

### 20-01 · `20-01-autonomy-tiers-and-escalation.ipynb` — The dial: risk tiers and confidence escalation
- **Type:** concept-lab
- **Maps to:** §20.1 (🧠 autonomy is a dial, not a switch; in/on/out-of-the-loop detents),
  §20.2 (approvals, reversibility, the risk-tier table; approval fatigue), §20.3 (escalation —
  the two independent triggers, confidence signals, the deferral threshold, `should_escalate`).
- **Objective:** classify actions on the *two* orthogonal axes — reversibility and confidence —
  and route to a human when *either* fires, with each trigger tuned separately.
- **Prereqs:** Ch 16 (verification — feeds confidence signals; `RunBudget`); Ch 13 (retrieval
  score as a signal); Ch 22 (evals — referenced, escalations become labeled data).
- **Cell arc:**
  - 🧠 mental model: calibrate agent autonomy like a new hire's — propose-and-approve on day
    one, keep approval rights over the expensive; make the dial explicit *in the architecture*.
  - The risk-tier table (§20.2): classify capstone tools by reversibility (read-only →
    reversible write → hard-to-reverse → irreversible) and read off the policy; note tiers
    attach to tools *and argument patterns* (a €10 vs €10,000 refund are different tiers).
  - ⚠️ pitfall: approval fatigue — gate too much and humans rubber-stamp within a week; a gate
    approving 99.8% of requests is a candidate for automation with sampled audits, not a control.
  - The second axis (§20.3): confidence — *is the agent probably wrong here?* — is orthogonal to
    reversibility; gating by risk alone sends confident-but-irreversible to a human and waves
    unsure-but-reversible straight through (backwards for the second failure).
  - Confidence signals (§20.3 table): model self-report, retrieval top score, verifier
    disagreement, self-consistency, ensemble, OOD, token logprobs — each a noisy proxy; combine
    two or three cheap ones, reserve the expensive ones for costly slices.
  - 🔮 *predict* which of a handful of mock decisions escalate, then run `should_escalate`
    (tier OR confidence < per-slice threshold) and check.
  - The threshold as a knob: over-defer (automation collapses, reviewers drown) vs under-defer
    (confident errors ship); tune against cost-of-wrong-answer and cost-of-human-time, per slice.
  - 🎯 senior lens: every escalation a human resolves is a *labeled hard case* — pipe it into the
    Ch 22 eval flywheel so the threshold can move *down* over time on evidence.
- **Datasets/fixtures:** a small in-cell list of mock decisions (tool + args + signal values) so
  the routing logic is deterministic and offline.
- **APIs & cost:** none/offline by design (the lesson is policy and signal-combination, not model
  calls); an optional cell sketches a live self-consistency vote behind `MOCK=0`.
- **You'll be able to:** tier any tool by reversibility, assemble a cheap confidence score, and
  set a per-slice deferral threshold that routes on *either* axis.

### 20-02 · `20-02-approval-gates-in-the-loop.ipynb` — 🔧 Build approval gates into the agent loop
- **Type:** walkthrough  *(this is the chapter's 🔧 Build — approval gates; §20.6, the escalation
  return-path mechanism from §20.3)*
- **Maps to:** §20.6 (🔧 Build: approval gates for high-risk tools — tier-aware executor,
  park-as-`waiting_human`, resume by injecting the decision as a tool result), §20.4
  (interruptibility & steering — cancel flag + message injection), §20.5 (trust surfaces:
  transparency, citations, explainability).
- **Objective:** wire the risk-tier table into the loop so gated calls checkpoint and pause for
  human approval, and an approval (or denial) resumes the run cleanly.
- **Prereqs:** 20-01; Ch 14 (checkpoint/resume — the mechanism this reuses); Ch 12 (the loop);
  Ch 16 (`RunBudget`); Ch 17 (the team whose tools get gated).
- **Cell arc:**
  - 🔧 `Tier` enum + `TOOL_TIERS` map (§20.6): `search_docs`/`get_ticket` READ,
    `create_ticket` REVERSIBLE, `send_reply`/`refund` GATED; unknown tools default to GATED.
  - The tier-aware `execute` (§20.6): on a GATED call, build a `PendingApproval` (run_id,
    tool_use_id, tool, args, *reasoning*), `store.save_pending`, set `status="waiting_human"`,
    checkpoint the run, and raise `NeedsApproval` instead of executing.
  - The resume path (§20.6): `resolve(...)` turns the human decision into the tool's result —
    approved calls execute now; denials inject an *error-shaped* result so the agent adapts
    (proposes an alternative, asks a question) rather than crashes; then `continue_run`.
  - 🔮 *predict* what the agent does when its `send_reply` is *denied with a reason*, then watch
    it re-plan from the injected error result.
  - Two design rules made concrete: approvals must carry enough context to judge (action, args,
    agent reasoning, consequences — never a bare "Approve?"); prefer *making actions reversible*
    (send delay + cancel, soft deletes, draft-first) over gating them.
  - Interruptibility & steering (§20.4): a cancel flag checked each iteration (a stop is "don't
    take the next step"); steering as a message injected before the next model call.
  - Trust surfaces (§20.5): stream progress ("Searching the document base… found 4 sources"),
    carry citations (the `CitedAnswer` contract from Ch 18), expose the agent's reasoning before
    approval — and treat self-reported reasoning as *evidence*, verifying what must be true (Ch 16).
  - ⚠️ pitfall (carried from 20-01): the audit log that "proves a human reviewed" a disaster
    nobody actually read — measure approval rates; retire rubber-stamp gates.
  - 🎯 senior lens: this gate is architecture you already had (checkpoints = pause, tool results
    = the human-decision channel, audit log already flowing to Ch 23); Part VII adds only the
    FastAPI endpoints, the Celery worker, and the notification job. On LangGraph, interrupts are
    this exact pattern as a framework feature (Ch 18).
- **Datasets/fixtures:** a tiny in-memory run store + a couple of tickets in `data/`; a mock LLM
  scripts a gated `send_reply` attempt so the pause/resume cycle is deterministic.
- **APIs & cost:** mockable (`MOCK=1` runs the full park→approve and park→deny cycles offline);
  live ≈ one short run that pauses at the gate. No real outbound actions — gated tools are mocks.
- **You'll be able to:** add reversibility-tiered approval gates to any agent loop, park and
  resume a run across an out-of-band human decision, and handle denial without crashing.

## Feeds (cross-pillar)
- **Blueprint(s):** the tier-aware executor + pause/resume hardens
  [`blueprints/agent-loop/`](../../blueprints/agent-loop/) and gates the team in
  [`blueprints/multi-agent-supervisor/`](../../blueprints/multi-agent-supervisor/).
- **Template(s):** the `Tier`/`TOOL_TIERS` + approval scaffold feeds
  [`templates/agent-project-starter/`](../../templates/agent-project-starter/).
- **Capstone:** builds `capstone-project/approvals.py` + the gate in `capstone-project/loop.py` (park as
  `waiting_human`, resume via injected tool result); the FastAPI approval endpoints + Celery
  `continue_run` dispatch land in Part VII. Checkpoint `checkpoints/ch20-approval-gates`.

## Dependencies
- Ch 14 (checkpoint/resume) · Ch 12 (the loop) · Ch 16 (`RunBudget`, verification) · Ch 17 (the
  team being gated) · Ch 13 (retrieval score signal). Feeds Part VII (endpoints + workers) ·
  Ch 22 (escalations → eval data) · Ch 23 (audit logging) · Ch 41 (compliance).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors, no live spend, and no real
      outbound actions (gated tools are mocked).
- [ ] `Tier`/`TOOL_TIERS`, the tier-aware `execute`, `PendingApproval`, and `resolve` match the
      book's §20.6 code; denial injects an error-shaped tool result, not a crash.
- [ ] Both axes are demonstrated — risk-tier gating *and* confidence escalation (`should_escalate`)
      — plus one full park→approve and one park→deny cycle.
- [ ] Recap + 2–4 exercises per notebook; secrets from env only; links resolve to
      `blueprints/agent-loop/`, `blueprints/multi-agent-supervisor/`, and `capstone-project/` approvals.
