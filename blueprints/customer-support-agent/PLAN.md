# Blueprint — Customer-Support Agent  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Support cost scales with headcount while ticket volume scales with growth; most tickets
are variations of a few dozen known questions plus a handful of routine actions. A head of
support/CX wants to break that coupling — deflect the repetitive, act on the simple, and
escalate the rest cleanly.

## What it does
A front-line agent (chat, email, or in-app widget) that **deflects** repetitive questions
with grounded, cited answers, **acts** on low-risk account changes (reset, refund-in-policy,
plan change, order check) through scoped tools, and **escalates** to a human when it should
not proceed. The autonomy dial starts at *answer-only* and adds actions once evals show the
agent matches human decisions (Appendix G → "Customer-support agent"; Ch 43 customer-facing
copilot pointed at support).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the tool-use decision loop that drives resolve/act/escalate.
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over help center, macros, and past resolved tickets so answers are grounded and cite a source (Ch 13).
- [`../mcp-server/`](../mcp-server/) — least-privilege tools into support/billing systems behind a clean tool boundary (Ch 19).
- [`../eval-harness/`](../eval-harness/) — the real-ticket eval set that gates every prompt/model change; measures resolution, not deflection (Ch 22).
- [`../observability-stack/`](../observability-stack/) — tracing to debug bad answers (Ch 23).
- *(reuses)* [`../llm-gateway/`](../llm-gateway/) — route easy turns to a cheap model, escalate hard ones (Ch 39–40).

## Planned structure
```text
customer-support-agent/
├── README.md                 # problem → solution → pitch (Phase 2)
├── PLAN.md                   # this file
├── app/
│   ├── support_agent.py      # wires agent-loop + rag-pipeline + tools
│   ├── policies.py           # escalation triggers (refund abuse, angry-customer)
│   └── decision.py           # structured resolve|act|escalate output schema (Ch 15)
├── tools/
│   └── billing_mock.py       # mock account/billing tools via mcp-server (gated actions)
├── evals/
│   └── tickets_golden.jsonl  # tiny golden set from synthetic tickets → eval-harness
├── data/
│   └── help_center/          # ~10 sample help-doc snippets + macros for rag-pipeline
└── demo.py                   # MOCK-mode run: 3 tickets (deflect / act / escalate)
```

## Maps to the book
- **Appendix G:** "Customer-support agent" (RAG + tools + HITL escalation; buyer = Support/CX).
- **Chapters showcased:** 13 (RAG), 12 (tool use), 20 (HITL escalation), 15 (structured
  decision), 19 (MCP), 25/38 (streaming chat surface), 22 (evals), 23 (tracing), 39/40
  (model routing), 41 (gating irreversible actions).

## How to adapt it
- Swap `data/help_center/` for your real help center + macro corpus.
- Replace `tools/billing_mock.py` with your support/billing MCP server; keep irreversible verbs behind the approval gate.
- Edit `policies.py` escalation triggers to your refund/abuse rules.
- Rebuild `evals/tickets_golden.jsonl` from *your* historical tickets — the eval is the contract.
- Tune the autonomy dial: start answer-only, enable actions per-type as evals clear the bar.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode (no API spend) and shows one deflect, one act, one escalate.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Composes the pattern blueprints via relative paths; does not fork them.
- [ ] Eval set gates a prompt/model change; resolution (not deflection) is the headline metric.
