# Intelligent Document Processing & Extraction — a *solution* blueprint

> Solution blueprint · realizes **Appendix G → "Intelligent document processing & extraction"** ·
> composes four pattern blueprints · showcases **Ch 45** (vision/OCR read), **Ch 15** (schema +
> repair), **Ch 20** (human review), **Ch 31/43** (batch fleet + manifest), **Ch 22** (golden-set evals).

This is not a new library — it is a **recipe** that wires existing pattern blueprints into a
product. It runs **free and deterministic** (`COMPANION_MOCK=1`, the default): no API keys, no
spend. Secrets come from the environment only when you opt into the live path.

---

## The problem (→ why anyone pays for this)

Back offices pay humans to retype information from documents — invoices, receipts, POs, forms,
statements, scanned PDFs — into a system of record. It is slow, expensive, error-prone, and
impossible to scale without linear headcount. The before-state is so concretely wasteful that
extraction is one of the most reliably lucrative agentic use cases (Appendix G). The hard part
is **not** the happy path; it is the last 20% — the misread digit, the dropped line, the poison
document — where the money and the lawsuits live.

## The solution (→ what this pipeline does)

An agentic pipeline that turns unstructured documents into **validated, structured data** with a
written escape hatch for everything it is not sure about:

1. **Read** the document (vision/OCR) as an **agent-loop** turn → a draft JSON object.
2. **Validate** it against a strict, **versioned** schema; on failure, **repair** by feeding the
   exact field-level errors back to the model and re-reading (bounded retries).
3. **Score confidence** from cheap, deterministic signals and **route** low-confidence items to a
   **human review queue** instead of auto-posting them.
4. **Drain a backlog** through a per-item **manifest** (resumable across crashes) with a
   **dead-letter** lane so one poison/oversize outlier can't wedge the other 999,999.
5. **Pick the model** with a **golden-set accuracy gate**: the cheapest model that still clears an
   explicit, written accuracy bar.

### It composes (does **not** fork) these pattern blueprints

| Part | Pattern blueprint | Role here | Book |
|------|-------------------|-----------|------|
| The read + repair control loop | [`../agent-loop/`](../agent-loop/) | `read_document` tool turn, turn cap, tool-error recovery | Ch 12 / 45 |
| The accuracy gate | [`../eval-harness/`](../eval-harness/) | golden set → field-accuracy grader → pick cheapest passing model | Ch 22 |
| Per-item audit + cost | [`../observability-stack/`](../observability-stack/) | trace each item (read → validate/repair), dead-letter visibility, $ roll-up | Ch 23 |
| The model door (live path) | [`../llm-gateway/`](../llm-gateway/) | model choice + metered inference for the worker fleet | Ch 39–41 |

The wiring is the whole integration: [`pipeline/_compose.py`](pipeline/_compose.py) puts each
sibling's `src/` on the path and the `pipeline.*` modules **import** them. A bug fixed in a
pattern is fixed here too.

---

## Quick start

```bash
# from this folder — no install needed; the compose seam shims the sibling src/ dirs onto the path
python demo.py
```

The demo drains the six sample documents in [`data/samples/`](data/samples/) and shows every
outcome the design must handle:

```
  [ACCEPT ] inv-1001   Acme Industrial Supply · USD 240.00 · conf 1.00
  [ACCEPT ] inv-1002   Globex Logistics · USD 1450.00 · conf 0.90 · repaired in 2 passes
  [REVIEW ] inv-1003   Initech Office Solutions · USD 1850.00 · conf 0.45 · why: line items miss the total by 35%
  [DEAD   ] inv-1004   error: vendor: expected a non-empty string …; currency: 'DOLLARS' is not ISO-4217 …
  [DEAD   ] inv-9999   error: oversize: 400 pages > 50 page limit        ← dead-lettered before any model spend
```

…then it proves **resumability** (re-run over the same manifest → all items skipped, zero
re-extraction), round-trips the manifest to JSONL, and prints the per-item **trace** with a
`$0.000000` cost roll-up (mock prices to zero).

Run the accuracy gate (picks the cheapest model that clears the bar):

```bash
python evals/eval.py
# Eval report … mean score 1.000 (threshold 0.90) … ✓ gate passed
# Model selection: 'claude-haiku-4' clears the 90% bar at $4.00/1M output tokens (cheapest passing).
```

---

## How it fits together

```text
document-extraction-pipeline/
├── README.md                       ← you are here
├── PLAN.md                         ← the spec (unchanged)
├── demo.py                         ← MOCK backfill: clean / repaired / review / dead-letter
├── pipeline/
│   ├── _compose.py                 ← the seam: sibling src/ → sys.path (import, never fork)
│   ├── __init__.py                 ← process_document() / run_backfill() orchestration
│   ├── schema.py                   ← strict, VERSIONED Invoice + validate (Ch 15)
│   ├── extract.py                  ← agent-loop read, traced, repair wired in (Ch 45)
│   ├── repair.py                   ← validate → repair → re-validate policy (Ch 15)
│   ├── confidence.py               ← score + route low-confidence → review queue (Ch 20)
│   └── manifest.py                 ← resumable per-item ledger + dead-letter lane (Ch 31/43)
├── evals/
│   ├── invoices_golden.jsonl       ← labeled golden set (clean / repairable / must-dead-letter)
│   └── eval.py                     ← golden-set gate; picks cheapest passing model (Ch 22)
└── data/samples/                   ← 6 mock docs incl. the poison 400-page outlier
```

**The public API** is two calls:

```python
from pipeline import Document, run_backfill, Manifest, ReviewQueue

docs = [Document(doc_id="inv-1001", source=open("data/samples/inv-1001-clean.txt").read())]
result = run_backfill(docs)                      # fresh run; manifest + review queue created
print(result.counts())                           # {'accepted': 1, 'review': 0, 'dead_letter': 0, …}

# Resume a crashed backfill — finished items are skipped:
m = Manifest.load("backfill.jsonl")
result = run_backfill(docs, manifest=m)
m.save("backfill.jsonl")
```

---

## How to adapt it to your domain

1. **Swap the schema.** Replace [`pipeline/schema.py`](pipeline/schema.py)'s `Invoice` with your
   document type's fields and constraints (claims, lending, logistics, KYC). In production make it
   a Pydantic `BaseModel` — the seam is one line (`Invoice.model_validate`) and nothing downstream
   changes (it only consumes the structured `ValidationError`).
2. **Write down the accepted error rate and the review path** up front, with the business owner.
   The accept threshold in [`pipeline/confidence.py`](pipeline/confidence.py) is the dial finance
   signs off on; [`evals/`](evals/) is how you set it honestly instead of by vibe. The last 20% is
   where the money and the lawsuits live — auto-posting it is the expensive mistake.
3. **Version the schema per item.** `SCHEMA_VERSION` stamps every record and the manifest, so a
   mid-backfill schema change is auditable, not silent — a million-doc backfill never finishes in
   one deploy.
4. **Configure the dead-letter rule** for poison/oversize docs (`MAX_DOC_PAGES` / `MAX_DOC_BYTES`
   in `manifest.py`) so one corrupt 400-page scan dead-letters instantly instead of melting a
   worker.
5. **Point the writer at your warehouse/ERP.** Today an `ACCEPT` calls `manifest.mark_accepted`;
   replace that with a transactional write to your system of record (Ch 30). Build the golden set
   from *your* labeled documents.

### Going live (opt-in, costs money)

By default everything runs offline (`COMPANION_MOCK=1`). To run a real model:

```bash
export COMPANION_MOCK=0
export ANTHROPIC_API_KEY=sk-…            # secrets from the env only; never committed
```

Then inject a vision-capable `ModelPort` (backed by [`../llm-gateway/`](../llm-gateway/)) where
`pipeline/extract.py` documents the seam (`build_mock_extractor_model` → your gateway port). The
agent loop, the repair policy, the confidence routing, the manifest, and the tracing are all
**unchanged** — only the model behind the read swaps. Under `COMPANION_MOCK=0` with no client
wired in, the pipeline **fails loud** rather than spending tokens behind your back.

---

## Maps to the book

- **Appendix G:** *Intelligent document processing & extraction* (extraction + schema validation;
  buyer = Finance / back-office ops).
- **Chapters showcased:** 45 (vision/OCR read), 15 (Pydantic schema + retry-and-repair), 20
  (human-review queue), 31/43 (worker fleet + manifest + batch), 22 (golden-set evals + model
  selection), 23 (observability), 30 (transactional write to the warehouse/ERP), 39–41 (the
  gateway on the live path).
