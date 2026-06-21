# Contract & Legal Review Assistant — a SOLUTION blueprint

> **Appendix G #4** · *Modern Agentic AI Engineer* companion repo.
> A **solution** blueprint: it does not introduce a new library — it **composes** four *pattern*
> blueprints into a working product. The agent **proposes**; a lawyer **disposes**.

```
extract  ──►  flag (cited)  ──►  redline (proposed)  ──►  human decides  ──►  audit trace
clause_schema   flags             review                  accept/edit/reject   observability
   Ch 15      rag-pipeline       agent-loop                 HITL · Ch 20/38      Ch 23
              Ch 13              Ch 16
```

---

## The problem

Contract review is slow, expensive, and bottlenecked on scarce legal time, so business deals sit
in a queue waiting for a first pass. Legal, procurement, and legal-ops teams don't want to *replace*
counsel — they want **leverage on expert time**: a dramatically shorter first-pass cycle where the
machine does the mechanical reading and the lawyer spends their judgment where it matters.

The trap is the obvious-but-wrong build: an LLM that "reviews the contract" and spits out prose.
That fails the only test that matters in legal — **can you trust it, and can you audit it?** A free-
text opinion with no citation is worse than useless; it's a liability. High value, high blast-radius
(Appendix G).

## The solution

An assistant that accelerates the first pass while keeping a human as the decision-maker:

1. **Extract** the contract into a typed, validated clause model — closed clause vocabulary, every
   clause text a verbatim span (no hallucinated citations). *(`app/clause_schema.py`, Ch 15.)*
2. **Flag** only the clauses that *deviate* from your playbook — and **every flag carries a
   citation**: the matched `RULE-ID`, its severity, and the standard position. An uncited flag is
   not representable in the type system. *(`app/flags.py`, grounded by the `rag-pipeline` blueprint,
   Ch 13.)*
3. **Redline** — for each flag, the `agent-loop` blueprint runs a critique→draft cycle and
   *proposes* an aligned edit. *(`app/review.py`, Ch 16.)*
4. **Decide** — every proposal starts `PENDING` and stays there until a person calls
   `accept()` / `edit()` / `reject()`. There is **no "accept all" and no auto-apply**. The data
   model makes the lawyer the decision-maker by construction. *(HITL — the product, Ch 20/38.)*
5. **Trace** — the whole run is one audit trace (flag → rule → redline) via the
   `observability-stack` blueprint, so every machine-proposed change is traceable to the rule that
   motivated it. *(Ch 23.)*

### How it composes (does **not** fork) the pattern blueprints

The integration *is* the wiring in `app/`. `app/_compose.py` puts each sibling pattern's `src/` on
`sys.path` and imports its package directly — a bug fixed in `agent-loop` is a bug fixed here.

| Pattern blueprint        | Role in this solution                                              | Chapter |
|--------------------------|-------------------------------------------------------------------|---------|
| [`rag-pipeline`](../rag-pipeline/)             | Hybrid retrieval over the risk playbook → grounds every flag      | 13      |
| [`agent-loop`](../agent-loop/)                 | The critique/redline loop that drafts an aligned edit             | 16      |
| [`observability-stack`](../observability-stack/) | One audit trace per contract: flag → rule → redline               | 23      |
| [`eval-harness`](../eval-harness/)             | Labeled clause golden set (`evals/clauses_golden.jsonl`)          | 22      |

## Run it (MOCK by default — offline, deterministic, **$0**)

```bash
cd blueprints/contract-review-assistant
python demo.py                    # COMPANION_MOCK=1 by default: no keys, no API spend
COMPANION_MOCK=0 python demo.py   # live path IF the pattern blueprints are wired to a keyed gateway
```

No module imports an SDK or spends a token in the default mode. Secrets, if any, come from the
environment — never hard-coded.

The demo reviews three committed sample contracts and you should see:

- `saas-agreement-clean.txt` → **0 flags** (it tracks the playbook — false positives erode trust as
  fast as misses do).
- `vendor-msa-redflags.txt` → **7 cited flags** across high/medium/low severity, a proposed redline
  for each, then a simulated lawyer accepting / editing / rejecting them.
- `services-agreement-mixed.txt` → **exactly 1 flag** (a Net 60 payment deviation), correctly cited
  to `RULE-PAY-001`.

## What's in here

```text
contract-review-assistant/
├── README.md                  # you are here
├── PLAN.md                    # the spec (unchanged)
├── demo.py                    # MOCK demo: extract → flag (cited) → redline → human decides → trace
├── app/
│   ├── __init__.py            # the one entry point: review_contract(doc_id, text) -> ReviewResult
│   ├── _compose.py            # the composition seam (pattern blueprints onto sys.path; no fork)
│   ├── clause_schema.py       # validated clause/term model + offline extractor   (Ch 15)
│   ├── flags.py               # cited deviation flags, grounded via rag-pipeline   (Ch 13)
│   └── review.py              # agent-loop critique → PENDING redline proposals    (Ch 16)
├── playbook/
│   └── risk_rules.md          # sample risk playbook + standard clause library (the RAG corpus)
├── evals/
│   └── clauses_golden.jsonl   # labeled clauses (known-bad + standard), eval-harness-loadable (Ch 22)
└── data/
    └── contracts/             # 3 sample contracts: clean, red-flagged, and mixed
```

## How to adapt it to your domain

This blueprint is a *recipe to copy and edit*, not a product to deploy. To point it at your work:

1. **Replace the playbook.** Swap `playbook/risk_rules.md` with **your firm's** negotiated positions
   and standard templates. Keep the `## RULE-XXX-NNN — Title (clause_type) — severity: level` heading
   shape — `app/flags.py` parses it and the citation excerpt is the rule's verbatim prose.
2. **Edit the clause vocabulary.** Change `ClauseType` and the extractor cues in
   `app/clause_schema.py` to the clause types *your* contracts care about (DPAs, SOWs, BAAs, …).
3. **Co-build the evals with counsel.** Extend `evals/clauses_golden.jsonl`. Keep both segments:
   `known-bad` clauses (must be flagged with the *right* rule) **and** `standard` clauses (must
   **not** raise a false flag). Run it through the [`eval-harness`](../eval-harness/) blueprint and
   gate releases on it — **every flag must carry a citation; uncited = failure.**
4. **Wire the accept/edit/reject UI.** `RedlineProposal.accept()/edit()/reject()` are the seam
   (Ch 20/38). The lawyer is the decision-maker — never ship a one-click "accept all".
5. **Go live deliberately.** Replace the offline extractor with a structured-output model call and
   the scripted `MockModel` in `app/review.py` with a gateway-backed model port. The loop, the tool,
   the schema, and the citation discipline are unchanged — only the model behind the seam changes.

## The non-negotiables (Phase-2 definition of done)

- **No uncited legal conclusions.** A `Flag` cannot be constructed without a `rule_id` +
  `rule_excerpt`; if nothing retrieves, the assistant emits *no* flag rather than an uncited one
  (fail closed).
- **The human stays the decision-maker.** The agent never advances a proposal past `PENDING`.
- **Confidentiality & tenancy is the career-ending risk.** Enforce per-matter / per-tenant
  isolation: one matter's contracts, playbook, and prior positions must never leak into another's
  retrieval index (Ch 41). The shipped demo builds a *single* in-memory index for clarity; in
  production, scope a `PlaybookIndex` per tenant/matter and never share the vector store across
  isolation boundaries.

---

*Maps to the book — Appendix G: "Contract & legal review assistant." Chapters showcased: 15
(clause schema), 13 (template/playbook retrieval), 16 (critique/redline loop), 20/38 (review UI:
accept/edit/reject), 41 (tenancy & confidentiality), 22 (evals with counsel), 23 (observability).*

> The sample playbook and contracts are **synthetic teaching artifacts, not legal advice.**
