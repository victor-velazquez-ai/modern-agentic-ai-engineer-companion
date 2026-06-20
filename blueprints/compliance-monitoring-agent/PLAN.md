# Blueprint — Compliance & Monitoring Agent  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Policy and compliance monitoring is manual, sampling-based, and cannot keep up with volume,
leaving gaps and slow detection. Risk, compliance, security, and trust-and-safety teams face
growing surveillance obligations with finite staff and want broader coverage, faster flagging,
and a defensible, auditable trail.

## What it does
An agent that continuously checks activity against policies and flags what needs attention:
reviewing communications or transactions for policy violations, classifying and routing
flagged items, maintaining audit trails, and surfacing anomalies for human investigation. The
core is **classification and policy-checking with reliable structured output**, grounded by
retrieval over the actual policies so flags are explainable and cite the rule. Human-in-the-loop
is essential — the agent flags and routes; humans adjudicate — and an **immutable audit trail
is part of the product** (Appendix G → "Compliance & monitoring agent").

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the classify → policy-check → route pass (structured, confidence-bearing).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over the policy corpus so every flag references the violated rule (Ch 13).
- [`../eval-harness/`](../eval-harness/) — evals built with compliance experts, tuned on the precision/recall trade-off appropriate to the obligation (Ch 22).
- [`../observability-stack/`](../observability-stack/) — the append-only audit log capturing every decision and its basis (Ch 28).

## Planned structure
```text
compliance-monitoring-agent/
├── README.md
├── PLAN.md
├── app/
│   ├── classify.py           # schema-validated classification + confidence (Ch 15)
│   ├── policy_check.py       # rag-pipeline: flag references the violated rule (Ch 13)
│   ├── route.py              # human review + adjudication queue (Ch 20)
│   └── anomaly.py            # model + simple statistical signals for anomaly surfacing
├── audit/
│   └── ledger.py             # append-only log of every decision + its basis (Ch 28)
├── policy/
│   └── policies.md           # sample policy corpus (the rule each flag must cite)
├── evals/
│   └── flags_golden.jsonl    # precision/recall-tuned labeled set (with experts)
├── data/
│   └── stream/               # ~8 mock messages/transactions (some violating)
└── demo.py                   # MOCK: screen the stream → flags w/ rule citations → audit entries
```

## Maps to the book
- **Appendix G:** "Compliance & monitoring agent" (classification + audit trail + HITL; buyer = Risk/compliance/security).
- **Chapters showcased:** 15 (structured, confidence-bearing classification), 13 (policy-corpus
  retrieval → explainable flags), 20 (human adjudication queue), 28 (append-only audit log),
  41 (access controls + data handling for sensitive inputs), 22 (precision/recall evals with
  experts).

## How to adapt it
- Replace `policy/policies.md` with your real policy corpus; wire connectors to your monitored streams (comms, transactions, access logs).
- **Tune precision/recall deliberately with stakeholders** — too many false positives buries the team; too many false negatives is a regulatory failure.
- Keep a human as the adjudicator of record; the agent flags and routes, it does not decide.
- Harden access controls + data handling — a monitoring agent that mishandles sensitive data is a breach, not a control.
- Co-build evals with compliance experts.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; screens the stream, flags items with rule citations, and writes audit entries.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Every flag cites a policy rule; audit log is append-only; human adjudication queue present; composes patterns without forking.
- [ ] Precision/recall-tuned eval set present.
