# Ch 13 — Retrieval-Augmented Generation (RAG)

> Companion plan · Part IV · book file `chapters/13-retrieval-augmented-generation.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is where the reader stops trusting the model's memory and starts grounding it in
*their* data. The notebooks turn the book's pipeline diagram into something you run: chunk a
real (messy) document, embed it, retrieve, rerank, and watch precision climb — then *measure*
the whole thing on a golden set, because the chapter's hard lesson is that RAG quality is
decided by retrieval, and retrieval is only as good as your evals. Together they build the
toy that the capstone's `rag/` module (the chapter's 🔧 Build) productionizes.

## Planned notebooks

### 13-01 · `13-01-chunk-embed-retrieve-rerank.ipynb` — The retrieval pipeline, end to end
- **Type:** walkthrough
- **Maps to:** book §13.2 (chunking), §13.3 (embeddings & similarity), §13.5 (hybrid search,
  reranking, query transformation) — the spine of RAG before the strategy menu.
- **Objective:** build a working retriever from raw text — parse → chunk → embed → vector
  search → rerank — and *see* each stage change which evidence reaches the model.
- **Prereqs:** Ch 11 (model APIs, embeddings) · `learn/part-03-llm-substrate/11-*`; the
  embedding intuition from Ch 8.
- **Cell arc:**
  - 🧠 mental model: the two halves (offline indexing vs online query path); "most quality
    problems live on the left half."
  - Parse one hostile-ish doc and run the book's paragraph-aware `chunk()` — inspect chunk
    sizes and overlap.
  - ⚠️ pitfall: read a *random sample* of the actual chunks; show a fixed-size splitter
    severing a table from its header vs. a structure-aware split.
  - Embed chunks + query with a small local model (`bge-small-en-v1.5`); compute cosine via
    normalized dot product; rank top-k.
  - 🔮 *predict*: for "how do I cancel my subscription?", will plain vector search beat the
    near-duplicate "upgrade" chunk? Run and see semantic-match ≠ relevance.
  - Add BM25 and fuse with **RRF** (hybrid) — show it rescue a literal `ERR_QUOTA_42` /
    SKU query that embeddings smear.
  - Stage a **cross-encoder reranker** over the top ~30 → keep top 6; compare the ordered
    list before vs after.
  - 🎯 senior lens: apply upgrades in cost-effectiveness order (hybrid → rerank → query
    transform); add one only when a metric demands it.
- **Datasets/fixtures:** a tiny committed `data/` corpus (a few short "product docs / policy"
  snippets, deliberately including identifiers and a near-duplicate pair).
- **APIs & cost:** offline-first — local sentence-transformers embeddings + reranker, no key
  needed; the optional query-rewrite step is `MOCK=1` canned, live ≈ 1 short call.
- **You'll be able to:** assemble a chunk→embed→retrieve→rerank pipeline and explain what
  each stage fixes.

### 13-02 · `13-02-grounded-answer-with-citations.ipynb` — 🔧 Build: grounded generation
- **Type:** walkthrough  *(the chapter's 🔧 Build — the capstone `rag/` retrieval+answer layer)*
- **Maps to:** book §13.8 "Build: production RAG over the capstone's private corpus"
  (the `Retriever` protocol, `ChromaRetriever`, and the cited-`answer()` function); §13.4
  (choosing a store) for *why* Chroma is the dev default behind an interface.
- **Objective:** wrap retrieval behind a `Retriever` protocol, index into Chroma, and
  generate an answer that **cites numbered sources** and declines when the sources don't cover
  the question.
- **Prereqs:** 13-01; Ch 12 tool-loop (retrieval will later become a tool, §13.6).
- **Cell arc:**
  - 🔧 define the `Hit` dataclass + `Retriever` Protocol — the seam agents/routes depend on,
    never Chroma directly.
  - Build `ChromaRetriever` (persistent client, cosine space); `index()` pre-chunked docs
    with `source`/`tags` metadata; `search(query, k, where=...)`.
  - Show **metadata filtering** as access control (`where` excludes docs a user may not see).
  - Assemble numbered context `[1] (source)\n…` and call the model with the book's
    grounding system prompt.
  - 🔮 *predict*: ask a question the corpus does **not** answer — does the model invent or
    decline? Then read the answer.
  - ⚠️ pitfall: drop the "say so if not in the sources" sentence and watch confident
    invention return — the cheapest hallucination defense is one line of system prompt.
  - 🎯 senior lens: the store choice is "another stateful system, or not?" — interface now
    so the Part VIII Pinecone swap is config, not a rewrite.
  - Close by pointing at `blueprints/rag-pipeline/` (hybrid + rerank + caching, productionized)
    and `capstone-project/rag/`.
- **Datasets/fixtures:** reuse 13-01's `data/` corpus, pre-chunked into `{id,text,source,tags}`.
- **APIs & cost:** local embeddings (offline) for indexing/retrieval; generation is `MOCK=1`
  canned by default, live ≈ 1–2 short messages.
- **You'll be able to:** stand up a swappable retriever and produce grounded, citable answers
  with an explicit "I don't know."

### 13-03 · `13-03-rag-eval-golden-set.ipynb` — Measuring RAG: the scorecard
- **Type:** concept-lab
- **Maps to:** book §13.8 "Evaluating RAG" — the RAG triad (context recall/precision,
  faithfulness, answer relevance) and the three-family scorecard (retrieval / generation /
  operational). (This is the §13.8 eval notebook called for in the brief.)
- **Objective:** build a small **golden set** and compute the retrieval metrics from set
  arithmetic, then gate the expensive LLM-judged generation metrics behind them.
- **Prereqs:** 13-02 (a working retriever to score).
- **Cell arc:**
  - 🧠 mental model: two coupled subsystems — a bad answer over perfect retrieval and a
    perfect answer over bad retrieval need *opposite* fixes; never collapse to one score.
  - Define a golden set: ~10–20 questions, each with the gold chunk id(s) + a reference
    answer (tiny, committed).
  - Compute **Hit Rate, Recall@k, Precision@k, MRR, nDCG@k** directly from retrieved vs gold
    ids — instant, free, deterministic.
  - 🔮 *predict*: shrink the chunk size / drop the reranker — which retrieval metric moves
    most? Re-run and confirm recall is the dominant cause of wrong answers.
  - **Generation metrics** (faithfulness, answer relevance) via an LLM judge — gated: only run
    if retrieval held; same judge + rubric every time.
  - Add the **operational** family (p95 latency, cost-per-query, index staleness) so "faithful
    but 4s at $1/query" registers as a failure too.
  - ⚠️ pitfall: a judge whose model/rubric drifts measures its own mood, not your system; and
    a single blended score hides which leg broke.
  - 🎯 senior lens: lead with the near-free retrieval metrics on every change; this golden set
    is what Ch 22 wires into CI so a recall-dropping tweak fails a build, not a customer.
- **Datasets/fixtures:** `data/golden_set.jsonl` (question, gold chunk ids, reference answer) —
  tiny and committed.
- **APIs & cost:** retrieval metrics fully offline; LLM-judge metrics `MOCK=1` canned by
  default (deterministic), live ≈ a handful of judge calls.
- **You'll be able to:** score a RAG change on a scorecard and say *which* subsystem regressed.

## Feeds (cross-pillar)
- **Blueprint(s):** [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/) — the
  production hybrid RAG (parse, structure-aware chunk, hybrid + rerank, query transform,
  retrieval cache, the `Retriever` interface). 13-01/13-02 end by pointing here.
- **Template(s):** — (contributes the grounding-prompt + citation pattern reused by
  agent service templates, but owns no template).
- **Capstone:** advances `capstone-project/rag/` (the `Retriever` protocol + `ChromaRetriever`, the
  cited `answer()`), and the eval golden set feeds `capstone-project/evals/` (Ch 22); checkpoint
  `checkpoints/ch13-rag`.

## Dependencies
- Ch 8 (embeddings intuition) · Ch 11 (model APIs, embedding calls, caching) · Ch 12 (tool
  loop — §13.6 reframes retrieval as a tool / agentic retrieval). Ch 14 reuses this exact
  retrieval machinery for long-term memory; Ch 22 builds the full eval harness around this
  golden set.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and no key (local
  embeddings + reranker; canned generation/judge).
- [ ] Chunker, `Retriever`/`ChromaRetriever` shapes, the grounding system prompt, and the
  scorecard metrics match the book's §13 code and terminology.
- [ ] 13-02 ends linking `blueprints/rag-pipeline/` and `capstone-project/rag/`; 13-03 links Ch 22.
- [ ] Each notebook ends with recap + 2–4 exercises; secrets from env only; golden set + corpus
  fixtures are tiny and committed.
