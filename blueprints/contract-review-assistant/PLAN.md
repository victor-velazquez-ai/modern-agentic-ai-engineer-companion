# Blueprint — Contract & Legal Review Assistant  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Contract review is slow, expensive, and bottlenecked on scarce legal time, so business deals
wait in a queue. Legal, procurement, and legal-ops teams want a dramatically shorter
first-pass cycle — leverage on expert time, not a replacement for it.

## What it does
An assistant that reads contracts and accelerates review: extracting key clauses/terms into
a structured model, flagging risky or non-standard language against a playbook, comparing
against a standard template, and proposing redlines — **always with a lawyer in the loop**.
Human-in-the-loop is the product, not a feature: the agent proposes, the lawyer disposes
(Appendix G → "Contract & legal review assistant"; high value, high blast-radius).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the reasoning/critique loop that compares clause-by-clause and drafts redlines (Ch 16).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over standard templates, prior negotiated positions, and the risk playbook so every flag is grounded and explainable (Ch 13).
- [`../eval-harness/`](../eval-harness/) — evals built *with counsel* on a labeled clause set and known-bad contracts (Ch 22).
- [`../observability-stack/`](../observability-stack/) — traceability of every flag → its source (audit posture).

## Planned structure
```text
contract-review-assistant/
├── README.md
├── PLAN.md
├── app/
│   ├── review.py             # agent-loop critique: clause-by-clause vs template (Ch 16)
│   ├── clause_schema.py      # validated clause/term extraction model (Ch 15)
│   └── flags.py              # each flag carries a citation + playbook rule (no uncited flags)
├── playbook/
│   └── risk_rules.md         # sample risk playbook + standard clause library (rag-pipeline)
├── evals/
│   └── clauses_golden.jsonl  # labeled clauses + known-bad contracts
├── data/
│   └── contracts/            # ~3 sample contracts (one with non-standard clauses)
└── demo.py                   # MOCK: extract clauses, flag deviations w/ citations, draft a redline
```

## Maps to the book
- **Appendix G:** "Contract & legal review assistant" (extraction + RAG + HITL redline; buyer = Legal/procurement).
- **Chapters showcased:** 15 (clause schema), 13 (template/playbook retrieval), 16
  (critique/redline loop), 20/38 (review UI: accept/edit/reject), 41 (tenancy &
  confidentiality), 22 (evals with counsel).

## How to adapt it
- Replace `playbook/risk_rules.md` and the clause library with your firm's standards and prior positions.
- Edit `clause_schema.py` to the clause types your contracts care about.
- Wire the accept/edit/reject UI so the lawyer is the decision-maker — never a one-click "accept all".
- Enforce per-matter / per-tenant isolation (confidentiality leakage is the career-ending risk).
- Co-build evals with counsel; **every flag must carry a citation** — uncited = failure.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; flags deviations, each with a source citation, and proposes a redline.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] No uncited legal conclusions; human remains decision-maker; composes rag-pipeline + agent-loop without forking.
- [ ] Confidentiality/tenancy note documented; eval set present.
