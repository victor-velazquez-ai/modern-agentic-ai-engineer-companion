# 🛡️ Blueprint — Compliance & Monitoring Agent (solution)

> Appendix G use case #12 · A **solution** blueprint: it *composes* four **pattern** blueprints
> into a product. Status: ✅ built · Runs **free & offline** (`COMPANION_MOCK=1`, the default).

```bash
python demo.py            # screen a mock stream -> flags w/ rule citations -> audit trail -> evals (MOCK, $0)
```

---

## The problem

Policy and compliance monitoring is manual, sampling-based, and can't keep up with volume — so
gaps open and violations are caught late. Risk, compliance, security, and trust-and-safety teams
have growing surveillance obligations and finite staff. They want **broader coverage**, **faster
flagging**, and — non-negotiably — a **defensible, auditable trail** for every decision.

## The solution

An agent that **continuously screens activity against policy and flags what needs attention**.
For each monitored item (a message, a transaction) it:

1. **retrieves the most relevant policy rule** — so every flag *cites the rule it broke*;
2. **classifies clear vs. flag** with a schema-validated, confidence-bearing verdict;
3. **adds a statistical anomaly signal** on transactions (outliers, threshold-hugging);
4. **routes flags to a human adjudication queue**, priority-ordered — the agent flags and
   routes; **a human decides**;
5. **writes an append-only, hash-chained audit record** of the decision and its basis.

The whole pass is wrapped in an **observability trace** (timing + cost), and the screener is
measured by an **expert-labeled, precision/recall-tuned eval set**.

```text
   monitored stream (comms / txns)
            │
            ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  Screener  (app/screen.py — the composition)                                   │
   │                                                                                │
   │   retrieve rule ─▶ classify clear/flag ─▶ anomaly? ─▶ route flag ─▶ audit       │
   │   (rag-pipeline)   (agent-loop)           (stats)     (HITL queue)  (ledger)    │
   │        │                │                                  │            │       │
   └────────┼────────────────┼──────────────────────────────────┼────────────┼──────┘
            │ policy_check    │ classify                          │ route       │ audit/ledger
            ▼                 ▼                                   ▼             ▼
     policy/policies.md   structured verdict              human review   append-only,
     (the cited rule)     {label,confidence,rule_id}      (adjudicates)  hash-chained log
                                                                          │
                       observability-stack: one run trace around it all ──┘  (cost = $0 in mock)
                       eval-harness: evals/flags_golden.jsonl  (precision vs. recall)
```

---

## Composes (pattern blueprints — imported, never forked)

This solution adds **no new mechanism**; it is the *wiring*. Each pattern is imported from
`../<pattern>/src` via `app.add_blueprint_paths()` (sibling `src/` onto the path — compose by
relative import, don't copy a line):

| Pattern blueprint | Role here | Wired in |
|---|---|---|
| [`rag-pipeline`](../rag-pipeline/) | Retrieve the policy rule each flag must cite (chunk → embed → hybrid retrieve → rerank). Hybrid earns its keep: violations hinge on *rare exact terms* ("OFAC", "MNPI", "10,000"). | [`app/policy_check.py`](app/policy_check.py) |
| [`agent-loop`](../agent-loop/) | The structured-output channel: the model's one legal move is to call `record_assessment` with a schema-valid verdict; the loop's malformed-call repair + turn cap come for free. | [`app/classify.py`](app/classify.py) |
| [`observability-stack`](../observability-stack/) | One run trace around the pass (retrieval / classify spans), with cost roll-up. | [`app/screen.py`](app/screen.py) |
| [`eval-harness`](../eval-harness/) | The expert-labeled golden set + graders; scored by precision (`must-clear`) and recall (`must-flag`). | [`evals/flags_golden.jsonl`](evals/flags_golden.jsonl) |

The two things that make it a *product* (not just a classifier) are owned here:

- **Human adjudication queue** — [`app/route.py`](app/route.py). Tickets ordered by severity ×
  confidence; the only decision the agent makes is *priority*, never the verdict.
- **Append-only audit ledger** — [`audit/ledger.py`](audit/ledger.py). Each record carries the
  SHA-256 of the previous one (a hash chain, Ch 28), so a silent edit anywhere breaks
  `verify()`. The trail is the deliverable, not an afterthought.

---

## What's in here

| Path | Role |
|---|---|
| [`app/screen.py`](app/screen.py) | **The composition.** `Screener` runs retrieve → classify → anomaly → route → audit per item, inside one trace. `classify_label` is the exact path the evals score. |
| [`app/policy_check.py`](app/policy_check.py) | `PolicyIndex` — the `rag-pipeline` indexed over the policy corpus; returns the rule a flag cites. |
| [`app/classify.py`](app/classify.py) | `Classifier` — schema-validated `{label, confidence, rule_id, reason}` via the `agent-loop`. Evidence-gated (a flag needs a concrete cue) with tunable **exoneration cues** for safe look-alikes. |
| [`app/route.py`](app/route.py) | `AdjudicationQueue` / `ReviewTicket` — the human review queue (HITL, Ch 20). |
| [`app/anomaly.py`](app/anomaly.py) | Robust-z (median/MAD) outlier + reporting-threshold-hugging signals — what a rule check misses. |
| [`audit/ledger.py`](audit/ledger.py) | `AuditLedger` — append-only, hash-chained, tamper-evident record; persists as JSONL. |
| [`policy/policies.md`](policy/policies.md) | The **sample policy corpus** (the rule each flag cites). Replace with yours. |
| [`evals/flags_golden.jsonl`](evals/flags_golden.jsonl) | The precision/recall-tuned golden set (tags: `must-flag` / `must-clear` + rule family). |
| [`data/stream/messages.jsonl`](data/stream/messages.jsonl) | ~8 mock messages/transactions, some violating. The file you swap for a real connector. |
| [`demo.py`](demo.py) | The runnable MOCK pass: screen → flags w/ citations → queue → audit → trace/cost → evals. |

---

## Why these design choices (the senior judgment)

- **Every flag cites a rule.** A flag that can't point at the rule it broke is unactionable for
  the adjudicator and indefensible to an auditor. Retrieval grounds the citation; the basis shown
  is the rule's own text.
- **The agent flags; a human decides.** There is deliberately *no* auto-close path. A monitoring
  agent that *decides* is a liability; one that *routes well* multiplies a finite team.
- **Precision is a first-class dial.** Too many false positives buries the team (and trains them
  to ignore the tool); too many false negatives is a regulatory failure. The classifier is
  **evidence-gated** and uses explicit **exoneration cues** so safe look-alikes (correct PII
  masking, risk-balanced return talk) clear — and the evals score `must-clear` and `must-flag`
  *separately* so you see which side moved. Tune this **with stakeholders**.
- **The audit trail is tamper-evident.** A hash chain makes a silent edit detectable; an audit log
  you could quietly change is not a control.
- **Free & deterministic by default.** Under `COMPANION_MOCK=1` the patterns fall back to their
  mocks (hash embedder, scripted model, console exporter), so the demo screens, flags, routes, and
  audits with **zero API spend**, identically every run.

---

## Run it / test it

```bash
python demo.py                    # the full pass, MOCK, $0  (writes dist/audit-ledger.jsonl)
COMPANION_MOCK=0 python demo.py   # live path: inject an llm-gateway model into Classifier(model=...)
```

The demo prints: the screening results (flags + citations + anomalies), the priority-ordered human
queue (with a human adjudicating two tickets), the append-only ledger and its `verify()` status,
the observability trace tree + cost roll-up, and the eval report broken down by precision/recall.

---

## How to adapt it to your domain

1. **Swap the policy corpus.** Replace [`policy/policies.md`](policy/policies.md) with your real
   policy/handbook/regulatory text — one rule per `## RULE-ID — title` heading. The `rag-pipeline`
   indexes whatever you put there; nothing else changes.
2. **Wire connectors to your streams.** Replace [`data/stream/messages.jsonl`](data/stream/messages.jsonl)
   with a connector to your monitored channels (comms, transactions, access logs). Feed each item
   to `Screener.screen(...)`.
3. **Tune precision/recall *with* stakeholders.** Co-build [`evals/flags_golden.jsonl`](evals/flags_golden.jsonl)
   with compliance experts, label real examples, and gate the build on it
   (`python -m eval_harness.gate evals/flags_golden.jsonl --baseline baseline.json`). Adjust the
   classifier's violation/exoneration cues (or, on the live path, the model + prompt) to move the
   trade-off where the obligation needs it.
4. **Keep a human as the adjudicator of record.** The agent enqueues `PENDING`; humans call
   `adjudicate(...)`. Don't add an auto-close.
5. **Harden data handling (Ch 41).** A monitoring agent reads sensitive inputs — apply access
   controls, scope what it can see, and mask PII in logs. A monitoring agent that mishandles
   sensitive data is a breach, not a control.
6. **Go live.** Inject an `llm-gateway`-backed `ModelPort` into `Classifier(model=...)`; the loop,
   tool schema, validation, routing, and audit ledger are unchanged — only the model behind the
   seam moves.

---

## Maps to the book

- **Appendix G #12** — "Compliance & monitoring agent" (classification + audit trail + HITL;
  buyer = Risk / compliance / security / trust-and-safety).
- **Chapters showcased:** **13** (policy-corpus retrieval → explainable flags), **15** (structured,
  confidence-bearing classification), **20** (human adjudication queue), **22** (precision/recall
  evals with experts), **28** (append-only audit log), **41** (access controls + data handling for
  sensitive inputs).
