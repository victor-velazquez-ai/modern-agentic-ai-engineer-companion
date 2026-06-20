# Blueprint — Research & Due-Diligence Agent  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Synthesis is slow and expensive: a human reads dozens of sources to produce one memo.
Analysts, consultants, strategy teams, and investment firms want a faster first draft of that
synthesis — the agent does the gather-and-summarize pass, the human does the judgment —
compressing days of reading into a reviewable, sourced draft.

## What it does
An agent that synthesizes an answer from many sources — internal documents, the web, filings,
data rooms — and produces a structured, **cited** brief (market scans, competitive research,
investment due diligence, vendor evaluations, literature reviews). A planner breaks the
question into sub-questions, retrieval/worker agents gather from each source, and a
synthesizer composes the cited brief with a reflection pass that checks claims against
sources. **Citations are the product** — without traceable sources the output is unusable
(Appendix G → "Research & due-diligence agent").

## Composes (pattern blueprints used)
- [`../multi-agent-supervisor/`](../multi-agent-supervisor/) — planner → retrieval/worker agents → synthesizer topology (Ch 17).
- [`../rag-pipeline/`](../rag-pipeline/) — internal-document retrieval; retrieval is central and citations are the product (Ch 13).
- [`../agent-loop/`](../agent-loop/) — per-worker tool use (web search, structured sources) + the verification/reflection loop (Ch 12, 16).
- [`../eval-harness/`](../eval-harness/) — evals on citation faithfulness and coverage (Ch 22).
- [`../observability-stack/`](../observability-stack/) — trace long runs; enforce step caps / cost controls (Ch 16, 40).

## Planned structure
```text
research-due-diligence-agent/
├── README.md
├── PLAN.md
├── app/
│   ├── planner.py            # decompose question → sub-questions (multi-agent-supervisor, Ch 17)
│   ├── workers.py            # retrieval/web/structured-source worker agents (Ch 12, 13)
│   ├── synthesize.py         # compose cited brief; every claim links to a source (Ch 15)
│   └── reflect.py            # verification pass flags unsupported/uncited claims (Ch 16)
├── evals/
│   └── faithfulness_golden.jsonl  # citation-faithfulness + coverage checks
├── data/
│   └── sources/              # ~6 mock source docs + a stubbed offline "web search"
└── demo.py                   # MOCK: question → sub-questions → cited brief (uncited = flagged)
```

## Maps to the book
- **Appendix G:** "Research & due-diligence agent" (multi-agent + cited RAG; buyer = Analysts/consulting/PE).
- **Chapters showcased:** 17 (supervisor/worker topology), 13 (central retrieval, citations),
  12 (web/structured-source tools), 15 (structured brief, claim→source links), 16
  (verification/reflection + step caps), 31 (durable long-running execution via queues), 40
  (cost controls), 22 (faithfulness/coverage evals).

## How to adapt it
- Swap `data/sources/` and the stubbed web search for your real corpora, filings, or data room.
- Tune the planner's decomposition depth and the worker fan-out to your question types.
- **Enforce that every claim is traceable to a retrieved source** — treat uncited claims as failures.
- Set step caps + cost guards so a research run cannot loop forever; measure coverage to avoid shallow stops.
- Run deep jobs durably via queues (minutes-long) instead of the demo's inline run.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; produces a cited brief where each claim links to a source.
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Uncited claims are flagged; step/cost caps enforced; composes multi-agent-supervisor + rag-pipeline without forking.
- [ ] Citation-faithfulness + coverage eval set present.
