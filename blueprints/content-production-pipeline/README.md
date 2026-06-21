# Content Production Pipeline — a *solution* blueprint

> A real-world agentic solution that **composes** the repo's pattern blueprints into one
> staged, human-in-the-loop content workflow. Maps to **Appendix G → "Content production
> pipeline"** and **Chapter 31** (queued/scheduled staged pipelines).

## The problem

Quality content is slow and expensive to produce, so volume, freshness, and personalization
all suffer. Marketing and content teams are under pressure to ship *more*, *faster*,
consistently *on-brand*, across *more channels* — and the naive fix (point an LLM at a topic
and publish) trades the speed for two new risks: **off-brand sameness** and **fabricated
claims** (a legal problem, not just a brand one).

## The solution

A pipeline, not a chatbot. From a brief it **researches, drafts, self-critiques, generates
channel variants, and runs brand + compliance guardrails** — then **stops at a human editor**.
People move from blank-page drafting to editing and approval.

```
brief ─▶ research ─▶ draft ─▶ critique ─▶ revise ─▶ variants ─▶ guardrails ─▶ REVIEW ─╳─ publish
        (rag)       (agent   (agent                (per          (brand +     (human)   (never
                     loop)    loop)                 channel)      compliance)            automatic)
```

Two properties carry the whole design:

1. **Grounded, so it can't fabricate.** Every draft is written from snippets retrieved out of
   your brand-voice + product-facts corpus. In MOCK mode the draft is *literally assembled from
   retrieved facts*, so it cannot assert a claim that isn't in the corpus — the property the
   retrieval is there to enforce.
2. **A human is the approval gate.** The run finishes `review_ready=True, published=False`. The
   pipeline never publishes; that is a deliberate, load-bearing line (Appendix G; Ch 20/38).

### It composes the pattern blueprints (it does not fork them)

The one composition seam is [`pipeline/compose.py`](pipeline/compose.py): it puts each sibling
blueprint's `src/` on `sys.path` and re-exports the symbols this solution uses. Every composing
module imports from there, so there is no vendored divergence.

| Pattern blueprint | Role here | Book |
|---|---|---|
| [`../agent-loop/`](../agent-loop/) | the per-stage draft + reflection/critique turns | Ch 16 |
| [`../rag-pipeline/`](../rag-pipeline/) | retrieval over brand guidelines + product facts (anti-fabrication) | Ch 13 |
| [`../eval-harness/`](../eval-harness/) | brand-adherence + factual-accuracy evals + a CI gate | Ch 22 |
| [`../observability-stack/`](../observability-stack/) | a span per stage → one auditable trace | Ch 23 |
| [`../llm-gateway/`](../llm-gateway/) | *(live path)* the single door for the model calls | Ch 40/41 |

## Run it (free, offline, deterministic)

No keys, no spend. `COMPANION_MOCK=1` is the default.

```bash
python demo.py              # the full walkthrough: a brief → review-ready variants + evals
python evals/run_evals.py   # just the brand + factual evals (exits non-zero on regression)
```

`demo.py` prints, in order: the loaded corpus, the per-stage **artifacts**, the channel
**variants**, the **guardrail** flags, the **trace + cost** ($0.00 in MOCK), the **review gate**
(`published=False`), a deliberate **guardrail catch** on off-brand copy, and the **evals**.

### The live path (opt-in, costs money)

Nothing calls an API by default. To run real model turns, inject a gateway-backed
[`ModelPort`](../agent-loop/src/agent_loop/model.py) into `ContentPipeline(model=...)`; the
stages don't change. The `llm-gateway` blueprint owns routing/caching/cost/guards, and secrets
come from the environment (e.g. `ANTHROPIC_API_KEY`) — never from the repo.

```python
from pipeline.corpus import load_brand_context, load_briefs
from pipeline.stages import ContentPipeline

brand = load_brand_context()
pipeline = ContentPipeline(brand, model=my_gateway_backed_port)  # MOCK when model=None
result = pipeline.run(load_briefs()[0])
assert result.review_ready and not result.run.published
```

## What's in here

```text
content-production-pipeline/
├── README.md                  # this file
├── PLAN.md                    # the spec (unchanged)
├── demo.py                    # MOCK walkthrough: brief → variants → flags → review-ready → evals
├── pipeline/
│   ├── compose.py             # the composition seam: import the blueprints, don't fork them
│   ├── stages.py              # brief → research → draft → critique → variants → guardrails → review
│   ├── critique.py            # the reflection/critique pass before a human sees it (Ch 16)
│   ├── guardrails.py          # brand + compliance output checks (Ch 41)
│   ├── artifacts.py           # one typed, inspectable artifact per stage (Ch 15)
│   └── corpus.py              # load brand/guidelines.md + data/briefs/*.json into blueprint types
├── brand/
│   └── guidelines.md          # sample brand voice + product-facts corpus (the rag grounding)
├── evals/
│   ├── brand_golden.jsonl     # brand-adherence + factual-accuracy golden set
│   └── run_evals.py           # runs the set via eval-harness; non-zero exit on regression
└── data/
    └── briefs/                # 3 sample briefs (blog / email / social)
```

## How to adapt it to your domain

1. **Swap the corpus.** Replace [`brand/guidelines.md`](brand/guidelines.md) with *your* brand
   voice + product truth. A strong grounding corpus is what keeps output distinctive instead of
   bland-at-scale. The retriever, chunking, and reranker are the unforked `rag-pipeline`.
2. **Tune the guardrails.** Edit [`pipeline/guardrails.py`](pipeline/guardrails.py) (`DEFAULT_RULES`
   or your own `GuardrailRules`) for your forbidden language, claim words, banned tone, and
   required disclaimers. Fabricated product claims are a legal risk — be conservative.
3. **Add your channels.** Extend the variant step in [`pipeline/stages.py`](pipeline/stages.py)
   for your channels/formats. **Keep the human approval gate before publish.**
4. **Grow the evals.** Add cases to [`evals/brand_golden.jsonl`](evals/brand_golden.jsonl) the day
   a draft goes off-brand. A grounding corpus + a human editor + a brand/factual eval set is the
   combination that beats sameness-at-scale.

## The pitch (who buys this)

Marketing / content teams who need to scale output **without** scaling brand and legal risk.
The win isn't "the AI writes the post"; it's that a grounded, guardrailed, *traceable* draft
lands on an editor's desk ready to approve — turning content production from blank-page drafting
into review-and-approve, with an audit trail for every claim.

## Maps to the book

- **Appendix G** — "Content production pipeline" (workflow + brand guardrails; buyer =
  Marketing/content).
- **Chapters:** 31 (staged/scheduled pipeline), 13 (brand-and-facts retrieval), 16
  (reflection/critique), 41 (brand/compliance guardrails), 15 (structured stage artifacts),
  20/38 (review-and-approve before publish), 22 (brand/factual evals), 23 (tracing the pipeline).
