# Customer-Support Agent — a SOLUTION blueprint

> **Appendix G #1** · *Solves · Approach · Build · Pitfalls* · Status: ✅ built (Phase 2, MOCK-runnable)

A front-line support agent that **deflects** repetitive questions with grounded, cited answers,
**acts** on low-risk account changes through scoped tools, and **escalates** to a human when it
should not proceed. This is a *solution* blueprint: it does not reinvent retrieval, tools, or
evals — it **composes the pattern blueprints** into one product. Runs **free, offline, and
deterministically** in MOCK mode (no API keys, no spend).

```bash
python demo.py            # three tickets: deflect / act / escalate
python demo.py --trace    # same, plus an observability span tree for one ticket
python demo.py --eval     # same, then score + gate against the golden set
```

---

## The problem

Support cost scales with headcount while ticket volume scales with growth — but most tickets are
variations of a few dozen known questions plus a handful of routine actions (reset a password,
check an order, refund within policy). A head of support/CX wants to **break that coupling**:
deflect the repetitive, act on the simple, and escalate the rest *cleanly* — without the agent
ever guessing a policy answer, arguing with an angry customer, or moving money it shouldn't.

## The solution

One ticket in, one **structured decision** out — exactly one of three verbs:

| Verb | When | How it's built |
|---|---|---|
| **RESOLVE** | An informational question the help center answers | hybrid retrieve + rerank (`rag-pipeline`), answer cited from the top source |
| **ACT** | A low-risk, in-policy account request (reset / order / plan / in-policy refund) | a scoped, validated tool call through the safe MCP boundary (`mcp-server`) |
| **ESCALATE** | Policy says stop (abuse, anger, out-of-policy/irreversible, refund over limit, weak grounding) | the escalation policy gate (`policies.py`), checked *before* any action |

The **autonomy dial** starts at *answer-only* and adds action types one at a time, as the eval
set shows the agent matches human decisions. Resolution (the *right* action, grounded when it
answers) — **not deflection rate** — is the headline metric.

```text
ticket ─► [escalation policy gate] ──fires──► ESCALATE
                 │ allows
                 ▼
          [classify intent]
                 │
   ┌─────────────┼──────────────────────────────┐
   ▼ informational              ▼ action request │
 [rag-pipeline retrieve+rerank] [scoped MCP tool] ──refused/fails──► ESCALATE
   │ grounded?                    │ acted
   ▼                              ▼
 RESOLVE (cited)                 ACT (confirmed)
```

## How it composes the pattern blueprints

It **imports** each pattern blueprint's published package (made importable by
[`app/_paths.py`](app/_paths.py), which puts each sibling's `src/` on `sys.path`). Nothing is
forked — change a pattern blueprint and this solution picks the change up.

| Pattern blueprint | Job here | Chapter |
|---|---|---|
| [`../rag-pipeline/`](../rag-pipeline/) | Ground answers in the help center + macros; cite a source (the *deflect* path) | 13 |
| [`../mcp-server/`](../mcp-server/) | Least-privilege tools into billing/account systems, behind an allow-list + validation + timeout | 19 |
| [`../agent-loop/`](../agent-loop/) | The tool-use loop substrate; its `ModelPort` is the seam a real model drives (see `build_action_loop`) | 12, 16 |
| [`../eval-harness/`](../eval-harness/) | The golden-ticket eval that gates every change; measures **resolution**, not deflection | 22 |
| [`../observability-stack/`](../observability-stack/) | Optional tracing — each ticket becomes a readable span tree (`--trace`) | 23 |
| [`../llm-gateway/`](../llm-gateway/) | *(reused, live path)* route easy turns to a cheap model, escalate hard ones | 39–40 |

## Files

```text
customer-support-agent/
├── README.md                    # this file
├── PLAN.md                      # the spec (unchanged)
├── demo.py                      # MOCK-mode run: deflect / act / escalate (+ --trace, --eval)
├── app/
│   ├── _paths.py                # composition seam: sibling blueprints onto sys.path (no fork)
│   ├── decision.py              # the resolve|act|escalate structured-output schema (Ch 15)
│   ├── policies.py              # escalation triggers (abuse, anger, refund limit, low grounding)
│   └── support_agent.py         # wires rag-pipeline + mcp tools + policy into one Decision
├── tools/
│   └── billing_mock.py          # scoped account/billing tools exposed over MCP (gated actions)
├── data/
│   ├── __init__.py              # load_help_center() → rag_pipeline.Document list
│   └── help_center/             # 10 help-doc snippets + a macros file (the RAG corpus)
└── evals/
    ├── run_eval.py              # candidate = the real agent; resolution grader + CI gate
    ├── tickets_golden.jsonl     # the golden set (the contract)
    └── baseline.json            # accepted scores (regenerated on first run)
```

## Run it

Everything is MOCK by default (`COMPANION_MOCK=1`):

- `python demo.py` — prints one **deflect** (cited answer), one **act** (in-policy refund via a
  scoped tool), one **escalate** (irreversible delete-account request).
- `python demo.py --eval` — runs the demo, then scores the agent over `evals/tickets_golden.jsonl`
  and **gates** the result. Exit code `0` = no regression, `1` = a score dropped past tolerance.
- `python evals/run_eval.py` — the gate on its own (what a CI step calls). First run writes
  `baseline.json`; later runs compare against it.

No keys are read and no network call is made on any of these paths. Secrets, when you go live,
come only from the environment.

## How to adapt it to your domain

1. **Swap the corpus.** Replace `data/help_center/` with your real help-center articles + macro
   library. The loader keys citations off the file stem and the first `# heading`; keep that or
   point `SupportAgent.from_help_center` at your own `rag_pipeline.Document` list.
2. **Swap the tools.** Replace `tools/billing_mock.py` handlers with calls into your real
   support/billing/CRM systems — or point the `SafeMCPClient` at your production MCP server over
   stdio/HTTP. **Keep every irreversible verb (refunds, deletions) behind the allow-list and the
   policy gate.**
3. **Edit the policy.** Tune `app/policies.py`: the `$50` refund auto-approve limit, the
   anger/abuse/out-of-policy keyword sets, the grounding floor. Each trigger is named data, so a
   new rule is one entry and the eval can target it by tag.
4. **Rebuild the eval from *your* tickets.** `evals/tickets_golden.jsonl` is the contract.
   Replace it with rows drawn from your historical tickets, label each with the action a human
   *would* take, and tag `must-escalate` cases. Then `python evals/run_eval.py --` gates every
   prompt/model change. **Resolution, not deflection** — a `must-escalate` case only passes if the
   agent escalated.
5. **Turn the autonomy dial.** Start answer-only: construct `SupportAgent` with `tool_caller=None`
   (every action then escalates). Enable one action type at a time — add its tool name to
   `tools.billing_mock.DEFAULT_ALLOWED_TOOLS` — only once the eval shows the agent matches human
   decisions for that type.
6. **Go live.** Inject a real model: route the answer-synthesis turn and (optionally) a
   model-driven action loop through `../llm-gateway/` and set `COMPANION_MOCK=0` with a key in the
   env. The composition seams (`ModelPort`, the embedder, the MCP transport) don't change.

## Pitfalls this blueprint is built to avoid

- **Deflection ≠ resolution.** An agent that "answers" a ticket it should have escalated looks
  great on deflection rate and terrible to the customer. The eval scores resolution, and a wrong
  action is a hard zero.
- **Acting when unsure.** The policy gate runs *before* any action, and the answer-only path
  escalates on weak grounding rather than guessing a policy.
- **Unscoped tools.** Actions are reachable only through the safe MCP client's allow-list +
  schema validation + timeout — discovery sees every tool, but an off-list tool can never reach
  the model.
- **Irreversible actions without a human.** Refunds over the limit, account deletion, and
  ownership transfers are escalation triggers, not tool calls.
