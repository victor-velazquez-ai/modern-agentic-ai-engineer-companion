# Blueprint — Intelligent Document Processing & Extraction  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Back offices pay humans to retype information from documents (invoices, receipts, POs, forms,
statements, scanned PDFs) into a system of record — slow, expensive, error-prone, and
impossible to scale without linear headcount. At volume it is one of the most reliably
lucrative agentic use cases because the before-state is so concretely wasteful.

## What it does
An agentic pipeline that turns unstructured documents into **validated structured data**
flowing straight into a system of record. It loads/OCRs documents, extracts into a strict
schema with type-checked validation and retry-and-repair, routes low-confidence items to a
human review queue, and (for backlogs) drains a queue with a per-item manifest for
resumability (Appendix G → "Intelligent document processing & extraction"; Ch 43 batch
pipeline when volume is high, synchronous service when per-transaction).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the extract → validate → repair control loop (multimodal/vision read for scans, Ch 45).
- [`../eval-harness/`](../eval-harness/) — labeled golden set to pick the cheapest model clearing the accuracy bar + ongoing sampling audits (Ch 22).
- [`../observability-stack/`](../observability-stack/) — per-item tracing, dead-letter visibility, drift detection.
- *(reuses)* [`../llm-gateway/`](../llm-gateway/) — model choice + batch inference for the worker fleet (Ch 31, 33, 39).

## Planned structure
```text
document-extraction-pipeline/
├── README.md
├── PLAN.md
├── pipeline/
│   ├── extract.py            # agent-loop: vision read → schema fill (Ch 45)
│   ├── schema.py             # strict Pydantic invoice/PO model, constrained fields (Ch 15)
│   ├── repair.py             # retry-and-repair on invalid output (Ch 15)
│   ├── confidence.py         # route uncertain items → human review queue (Ch 20)
│   └── manifest.py           # per-item manifest for resumable backfill (Ch 31, 43)
├── evals/
│   └── invoices_golden.jsonl # labeled fields for accuracy/cost evals
├── data/
│   └── samples/              # ~6 mock docs incl. one "poison" 400-page/corrupt outlier
└── demo.py                   # MOCK: extract 3 docs, 1 passes, 1 repairs, 1 dead-letters
```

## Maps to the book
- **Appendix G:** "Intelligent document processing & extraction" (extraction + schema validation; buyer = Finance/back-office ops).
- **Chapters showcased:** 45 (vision/OCR), 15 (Pydantic schema + repair), 20 (human-review
  queue), 31/33/43 (worker fleet + manifest + batch), 22 (golden-set evals + audits), 30
  (transactional write to warehouse/ERP).

## How to adapt it
- Replace `schema.py` with your document type's fields and constraints (claims, lending, logistics).
- Set the **accepted error rate and human-review path in writing** up front — the last 20% is where the money and lawsuits live.
- Version the schema per item to survive schema drift mid-backfill.
- Configure the dead-letter rule for poison/oversized documents so one outlier can't wedge the pipeline.
- Point the writer at your warehouse/ERP; build the golden set from *your* labeled docs.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; shows a clean extract, a repaired one, and a dead-lettered poison doc.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Schema is versioned per item; confidence routing to a review queue works; composes patterns without forking.
- [ ] Golden-set eval picks a model against an explicit accuracy bar.
