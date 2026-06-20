# rag-pipeline — hybrid retrieval, as a senior would build it

> **Pattern blueprint** · Realizes book **Ch 13 — Retrieval-Augmented Generation** · mirrors
> capstone [`rag/`](../../capstone) · composes [`llm-gateway`](../llm-gateway/) (optional, for
> real embeddings / LLM reranking)

A complete, typed, **runnable** retrieval pipeline — `chunk → embed → retrieve → rerank` — with a
vector store behind an adapter so local ↔ cloud is a one-line swap. It runs **free and offline by
default** (`COMPANION_MOCK=1`): deterministic embeddings, no API spend, no network. This is the
standalone "how a senior structures retrieval" that the Ch 13 notebooks build toward and that the
solution blueprints (customer-support, internal-knowledge, contract-review, incident-response…)
compose.

> Blueprints are **study-and-adapt reference code, not an answer key**. Read it by *running* it,
> then lift the structure into your own system. (See [`../README.md`](../README.md).)

```text
ingest ──▶ embed ──▶ ┌──────── retrieve (hybrid) ────────┐ ──▶ rerank ──▶ top-k to the model
 chunk     vectors    │  dense (cosine)  keyword (IDF)    │    reorder
                      │        └──── RRF fusion ────┘     │
                      └──────────── VectorStore ──────────┘
                              memory (default) │ chroma (opt) │ pinecone (swap)
```

## Quickstart

```bash
# zero setup, zero spend, deterministic:
python demo.py

# run the tests (pure stdlib; pytest only):
python -m pytest -q
```

```python
from rag_pipeline import (
    Document, chunk_documents, embed_chunks,
    InMemoryVectorStore, HybridRetriever, MockReranker,
)

store = InMemoryVectorStore()
store.add(embed_chunks(chunk_documents([Document(id="d1", text="...your corpus...")])))

retriever = HybridRetriever(store)
hits = retriever.retrieve("your question", k=5)        # dense + keyword, RRF-fused
answers = MockReranker().rerank("your question", hits) # precision pass before the model
```

The package has **no required runtime dependencies** — in `MOCK` mode it imports only the
standard library. Optional integrations (`chromadb` for persistence, the `llm-gateway` blueprint
for real embeddings/reranking) are imported lazily and pulled from the repo-wide
`requirements.txt`.

## What each stage does — and the trade-off it forces

### 1. `ingest.py` — chunking is the decision that bounds everything downstream
A retriever can only return what ingestion preserved. Chunks must be **small enough to be
specific** yet **large enough to stand alone**, with **overlap** so a fact split across a boundary
survives in at least one chunk.

| Knob | Smaller | Larger |
|---|---|---|
| **chunk size** | sharper match, more precise citations; risks losing context around the hit | more self-contained context; dilutes the match and wastes prompt tokens |
| **overlap** | fewer tokens stored/embedded (cheaper) | better boundary recall; more duplication and cost |

Defaults here (`~120 words`, `~20 overlap`) sit in the book's rule-of-thumb band (~200–400 tokens,
10–20% overlap). `structure_aware=True` splits on the document's own paragraph seams first and only
windows paragraphs that overrun — almost always better than blindly windowing prose. Guarantees the
tests pin: **no word is lost**, and consecutive windows share exactly `overlap` words.

### 2. `embed.py` — one embedder interface, mock by default, real through the gateway
`Embedder` is a tiny `Protocol`. The default `MockEmbedder` is **deterministic feature hashing**:
same text → same unit vector, and more shared words → higher cosine, so neighbors are *sensible*,
not just reproducible. It is **not** a learned model (no synonymy) — it exists so the pipeline is
honest to run for free. With `COMPANION_MOCK=0`, `get_embedder()` borrows a real embedder from the
[`llm-gateway`](../llm-gateway/) blueprint if it is on the path and keyed; otherwise it transparently
falls back to the mock, so nothing ever breaks at import time.

### 3. `stores/` — the store is an adapter, not a dependency
`VectorStore` (a `Protocol` in `stores/base.py`) is the seam that keeps retrieval ignorant of *where*
vectors live. Three positions on one interface:

| Adapter | When | Notes |
|---|---|---|
| `InMemoryVectorStore` (default) | tests, notebooks, small corpora (≤ a few thousand chunks) | pure Python, exact, deterministic, zero deps |
| `ChromaVectorStore` | local persistence, larger corpora | lazy-imports `chromadb`; cosine space to match the in-memory ranks |
| **Pinecone (the swap)** | cloud scale, managed | *another adapter* implementing the same 3 methods — see below |

**Store-adapter swap (local ↔ cloud).** Going to the cloud is a new adapter, **not a rewrite**. A
`PineconeVectorStore` implements the same surface: `add → upsert`, `search → query`, and
`keyword_search → ` a metadata/sparse query or a sidecar BM25 index. Construction changes from
`ChromaVectorStore(...)` to `PineconeVectorStore(...)`; the retriever, reranker, and demo do not
change a line. That is the whole point of the Protocol.

### 4. `retrieve.py` — hybrid search, fused with RRF
Dense retrieval nails *meaning* and fumbles *exact terms* (an error code, an order id, a rare
noun); keyword retrieval is the mirror image. **Hybrid runs both and fuses them.** Fusion is
**Reciprocal Rank Fusion**: `score = Σ 1/(k + rank)` across channels — it combines *ranks*, so the
two channels never need a shared score scale (the perennial headache of weighted score blending).
A doc near the top of *either* list scores well; near the top of *both* wins.

The keyword channel here is **IDF-weighted** (BM25's ranking core): a rare term contributes far
more than a common one, which is precisely why hybrid beats dense-only on keyword-y queries.
`demo.py` shows it live — for the query `"QX77 gateway"`, dense-only ranks the real answer **3rd**
(fooled by docs that flood the common word *gateway*); the keyword channel ranks it **1st** on the
rare code *QX77*; fused, it climbs to the top.

**Dense vs. hybrid — when to bother.** If your queries are natural-language and your corpus is
prose, dense alone is often fine. Add the keyword channel when **exact tokens matter**: codes, IDs,
SKUs, names, jargon, code symbols. It is cheap (one extra lexical pass) and rarely hurts, so the
senior default for support/knowledge/ops corpora is *hybrid on*.

### 5. `rerank.py` — precision pass, only on a short list
Retrieval optimizes **recall** (cast a wide, cheap net); a reranker optimizes **precision** (score
each shortlisted chunk against the query with a stronger model and reorder). The default
`MockReranker` is a deterministic, explainable lexical scorer (query-term **coverage** + **density**,
stopwords stripped) — a stand-in for the real cross-encoder / LLM reranker, which would implement the
same `Reranker` protocol and run through the `llm-gateway`.

**When reranking earns its latency.** A reranker is expensive per (query, chunk) pair, so it pays
off only on a **short** candidate list — rerank the top ~20–50, never the corpus. Reach for it when
retrieval has decent recall but mediocre ordering (the right chunk is in the top-20 but not the
top-3), when you can only fit a few chunks in the prompt, or when answer quality is worth ~100–300ms
and a few cents per query. Skip it when retrieval is already precise or latency is sacred. In
`demo.py` the rerank pass takes the hybrid shortlist and lifts the true answer from #2 to #1.

## Composition

- **[`llm-gateway`](../llm-gateway/)** — the single door to model calls. This pipeline asks it for a
  real embedder (and optionally an LLM reranker) when `COMPANION_MOCK=0`; the mock embedder/scorer
  keep the pipeline fully runnable **standalone** when the gateway isn't wired in. The import is
  lazy and best-effort (`embed._try_gateway_embedder`), so a missing gateway never breaks this
  package.
- **Foundational for retrieval** — solution blueprints depend on `rag-pipeline`, not the reverse.

## Reproducibility & cost (per `docs/NOTEBOOK-STANDARDS.md`)

- **MOCK by default.** `COMPANION_MOCK=1` (the repo default) → deterministic embeddings + scorer,
  **no API spend**, no network, identical results every run.
- **Secrets from env only.** Nothing is hardcoded; `MOCK=0` is the only path that reads keys, via the
  gateway. See [`.env.example`](../../.env.example).
- **Deterministic ordering.** Every ranked list breaks ties on chunk id, so tests and demos are
  reproducible across machines.

## Run the tests

```bash
python -m pytest -q
# tests/test_chunking.py  — boundaries, overlap, no-loss, stable ids
# tests/test_retrieve.py  — hybrid beats dense-only on a keyword-y query; RRF fusion
# tests/test_rerank.py    — rerank reorders the shortlist as expected
```

## Maps to the book & capstone

- **Ch 13 — RAG:** loaders, chunking, embeddings, vector stores, hybrid search, reranking. Makes
  §13's 🔧 Build sections real.
- **`learn/` walkthrough:**
  [`../../learn/part-04-building-blocks-of-agents/13-retrieval-augmented-generation/`](../../learn/part-04-building-blocks-of-agents/13-retrieval-augmented-generation/)
  builds chunk→embed→retrieve→rerank as a guided exercise and **ends by pointing here**.
- **Capstone `rag/`:** this is the standalone version — `ingest/` (loaders, chunking, embedding),
  `stores/` (Chroma local + Pinecone cloud adapters), and `retrieve.py` (hybrid + rerank).

## How to adapt it

1. Replace the demo corpus with your documents; add a real loader in `ingest.py` (Markdown/HTML/PDF
   → text) feeding `chunk_documents`.
2. Tune `chunk_size`/`overlap` to your content (tables and code want larger, structure-aware chunks).
3. Set `COMPANION_MOCK=0` and wire the `llm-gateway` to swap the mock embedder for a real model.
4. Swap `InMemoryVectorStore` → `ChromaVectorStore(persist_directory=...)` for persistence, or write
   a `PineconeVectorStore` against the same `VectorStore` Protocol for cloud scale.
5. Replace `MockReranker` with a cross-encoder or an LLM reranker through the gateway; keep the
   candidate list short.
