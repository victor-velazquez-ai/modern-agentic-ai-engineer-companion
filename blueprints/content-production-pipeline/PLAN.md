# Blueprint — Content Production Pipeline  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Quality content is slow and expensive to produce, so volume, freshness, and personalization
all suffer. Marketing and content teams are under pressure to produce more, faster,
consistently on-brand, and across more channels.

## What it does
An agentic pipeline that scales content creation: from a brief or topic it researches, drafts,
generates variants and channel adaptations, and applies brand and compliance guardrails —
**keeping a human as editor**. It is a workflow more than a chat: brief → research → draft →
variants → guardrail check → human review, with a reflection/critique pass improving drafts
before a human sees them. Humans move from blank-page drafting to editing and approval
(Appendix G → "Content production pipeline"; Ch 31 workflow).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — the per-stage draft + reflection/critique loop (Ch 16).
- [`../rag-pipeline/`](../rag-pipeline/) — retrieval over brand guidelines, prior content, and product facts to prevent off-message/fabricated claims (Ch 13).
- [`../eval-harness/`](../eval-harness/) — evals on brand adherence and factual accuracy (Ch 22).
- [`../observability-stack/`](../observability-stack/) — trace the staged pipeline; inspect each artifact.
- *(reuses)* [`../llm-gateway/`](../llm-gateway/) — model choice across draft/variant stages.

## Planned structure
```text
content-production-pipeline/
├── README.md
├── PLAN.md
├── pipeline/
│   ├── stages.py             # brief → research → draft → variants → guardrail → review (Ch 31)
│   ├── critique.py           # reflection/critique pass before human review (Ch 16)
│   ├── guardrails.py         # brand+compliance output checks: tone, claims, forbidden language (Ch 41)
│   └── artifacts.py          # structured artifact per stage → auditable pipeline (Ch 15)
├── brand/
│   └── guidelines.md         # sample brand voice + product facts corpus (rag-pipeline)
├── evals/
│   └── brand_golden.jsonl    # brand-adherence + factual-accuracy checks
├── data/
│   └── briefs/               # ~3 sample briefs/topics
└── demo.py                   # MOCK: brief → draft + variants → guardrail flags → review-ready
```

## Maps to the book
- **Appendix G:** "Content production pipeline" (workflow + brand guardrails; buyer = Marketing/content).
- **Chapters showcased:** 31 (queued/scheduled staged pipeline), 13 (brand-and-facts
  retrieval), 16 (reflection/critique), 41 (brand/compliance guardrails), 15 (structured
  stage artifacts), 20/38 (review-and-approve UI before publish), 22 (brand/factual evals).

## How to adapt it
- Replace `brand/guidelines.md` and the facts corpus with your brand voice + product truth.
- Edit `guardrails.py` for your forbidden language, claim rules, and tone — fabricated product claims are a legal as well as brand risk.
- Add your channels/variants to `stages.py`; keep the **human approval gate before publish**.
- Build brand-adherence + factual evals; a strong grounding corpus + human editor is what keeps output distinctive (vs bland sameness-at-scale).

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; produces a draft + variants with guardrail flags, marked review-ready (not published).
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Brand/compliance guardrails + human approval gate present; composes agent-loop + rag-pipeline without forking.
- [ ] Brand-adherence + factual-accuracy eval set present.
