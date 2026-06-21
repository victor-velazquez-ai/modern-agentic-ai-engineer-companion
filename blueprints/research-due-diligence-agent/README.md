# Research & Due-Diligence Agent (solution blueprint)

> **Appendix G use case #8** — *Research & due-diligence agent.* A **solution** blueprint:
> it does not invent new mechanisms, it **composes pattern blueprints** into a product.
> Buyer: analysts, consulting, strategy teams, PE / corp-dev. Maps to **Ch 17, 13, 12, 15, 16,
> 22, 23, 40**.

---

## The problem

Synthesis is slow and expensive. A human reads dozens of sources — data-room documents,
filings, market reports, reference calls — to produce **one** memo. Analysts, consultants, and
investment teams want a faster *first draft* of that synthesis: the agent does the
gather-and-summarize pass, the human does the judgment. The catch that makes this hard to ship:
**citations are the product.** A brief whose claims you cannot trace back to a source is
useless for diligence — worse than useless, because it *looks* authoritative.

## The solution

An agent that decomposes a research question, fans retrieval workers across many sources, and
synthesizes a **cited** brief — then **verifies its own work**, flagging any claim that is not
grounded in a retrieved source.

```text
question ─▶ PLAN ─▶ fan-out WORKERS ─▶ SYNTHESIZE ─▶ REFLECT ─▶ cited brief
           (sub-Qs)  (retrieve+cite)    (claims→src)   (verify)   + flags
           └──────────────── traced, with step + cost caps ───────────────┘
```

| Step | What happens | Composes (pattern blueprint) |
|---|---|---|
| **Plan** | Break the question into bounded sub-questions | `multi-agent-supervisor` (`SubTask`, `IterationGuard` step cap) |
| **Delegate & fan out** | Run sub-questions in parallel waves; isolate worker failures | `multi-agent-supervisor` (`run_isolated`) |
| **Gather evidence** | Hybrid retrieve → rerank → cited passages; offline "web search" stub | `rag-pipeline` (`HybridRetriever`, `MockReranker`) + `agent-loop` (tool-use seam) |
| **Synthesize** | Compose claims, **each linked to a source id** | `synthesize.py` (Ch 15) |
| **Reflect / verify** | Flag uncited or unsupported claims | `reflect.py` (Ch 16 reflection loop) |
| **Observe & cap** | Trace the run; attach token/cost; enforce **step + cost caps** | `observability-stack` (`Tracer`, `summarize`) |
| **Evaluate** | Score citation-faithfulness + coverage; CI gate | `eval-harness` (`Case`, `Contains`, `run`) |

The pattern blueprints are **imported, never forked** — `app/_compose.py` puts each sibling's
`src/` on the path, so editing a pattern blueprint flows straight through to this solution.

## Run it (MOCK mode — no API key, no spend)

Everything runs **free, offline, and deterministically**; `COMPANION_MOCK` defaults to `1`.

```bash
cd blueprints/research-due-diligence-agent
python demo.py                                   # default question (acquire Acme?)
python demo.py "Evaluate Acme Vector DB Inc."    # your own question
python evals/run_evals.py                         # coverage + faithfulness gate
```

The demo prints a **cited brief**, runs the **verification pass** (12/12 claims grounded on the
sample corpus), then injects one *uncited* claim and shows the reflection pass **catching it**
(the demo exits non-zero if the guard ever fails to catch it — usable as a smoke test).

### What the sample data is

`data/sources/` holds six mock documents about a fictional target, *Acme Vector DB Inc.*: two
internal data-room memos (`internal-*`) and four "web" briefs (`web-*`) covering market,
competition, customers, and risks. `data/web_index.json` decorates the web docs with
titles/urls so the **stubbed offline web search** can present results that *look* like a search
page — with **no network call**. Retrieval itself is hybrid search over the document text.

## Files

```text
research-due-diligence-agent/
├── README.md            ← you are here
├── PLAN.md              ← the spec (unchanged)
├── demo.py              ← MOCK demo: question → cited brief; uncited claim flagged
├── app/
│   ├── _compose.py      ← puts sibling pattern-blueprint src/ on sys.path (the seam)
│   ├── corpus.py        ← load data/sources/ → rag-pipeline store (composes rag-pipeline)
│   ├── planner.py       ← question → sub-questions (composes multi-agent-supervisor)
│   ├── workers.py       ← retrieval/web workers → cited Evidence (rag-pipeline + agent-loop)
│   ├── synthesize.py    ← evidence → CitedBrief (every claim → source)
│   ├── reflect.py       ← verification pass: flag uncited / unsupported claims
│   └── pipeline.py      ← end-to-end run, traced, step + cost caps (observability-stack)
├── evals/
│   ├── faithfulness_golden.jsonl   ← coverage + faithfulness golden set
│   └── run_evals.py                ← scores it via eval-harness (CI gate)
└── data/
    ├── sources/*.md     ← 6 mock source docs (internal + web)
    └── web_index.json   ← stubbed offline "web search" metadata
```

## How to adapt it to your domain

1. **Swap the corpus.** Drop your real documents into `data/sources/` (or point
   `build_agent(sources_dir=...)` at your data room / export). Internal docs are recognized by
   an `internal-` id prefix; everything else is treated as "web." Replace the stubbed web search
   with a real search tool by giving `RetrievalWorker` a tool that hits your search API.
2. **Tune the question shape.** The planner expands a fixed set of **facets** (overview,
   financials, market, competition, customers, risks) in `app/planner.py`. Edit `_FACETS` to
   match your question types — a literature review needs different facets than a vendor eval.
   Tune the worker fan-out (`top_k` / `top_n`) for your corpus size.
3. **Treat every uncited claim as a failure.** The reflection pass (`app/reflect.py`) is the
   non-negotiable part. Keep `grounding_threshold` strict; for higher-stakes work add an
   LLM-judge from `eval-harness` for semantic entailment on top of the lexical grounding check.
4. **Keep the caps on.** `max_steps` (step budget) and `max_cost_usd` (cost budget) in
   `build_agent` stop a run from looping forever or quietly overspending. Measure **coverage**
   (did you retrieve the source that holds the answer?) so the agent does not stop shallow.
5. **Go durable for real jobs.** The demo runs inline; a minutes-long research job belongs on a
   queue (Ch 31). The pipeline returns a plain `DueDiligenceReport`, so persisting/streaming it
   from a worker process is a drop-in.

## Going live (optional, billed)

Set `COMPANION_MOCK=0` and `ANTHROPIC_API_KEY=...` to use real models. The composition seam is
unchanged: the mock embedder/reranker/synthesis are replaced by the real ones through
`llm-gateway`, and the worker's tool loop can drive a live `agent_loop.AgentLoop`. The
orchestration in `pipeline.py` does not change — that is the point of composing against
interfaces.
