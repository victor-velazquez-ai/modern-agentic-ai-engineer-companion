# Blueprint — RAG Pipeline  (pattern)

> Realizes book Ch 13 · mirrors capstone `rag/` · Status: 📋 planned (Phase 1)

## What it is
A complete **hybrid retrieval pipeline**: `chunk → embed → retrieve → rerank`. Document loaders
and a chunking strategy, an embedding step, a vector store behind an adapter (local default +
cloud option), **hybrid search** (dense + keyword) fused, and a **reranker** that reorders the
shortlist before it reaches the model. The standalone "how a senior structures retrieval."

## Why a blueprint (not a notebook)
- The Ch 13 notebooks teach chunking and retrieval one knob at a time; the *whole assembled
  pipeline* — ingest job, store adapter, hybrid fusion, rerank — is only honest as a package.
- Several solution blueprints (support, knowledge assistant, contract review, incident copilot)
  **compose** it, so it needs a stable, importable surface.
- Store portability (local Chroma ↔ cloud Pinecone) is an adapter decision that must live in
  real code with tests, not prose.

## Planned structure
```text
rag-pipeline/
├── README.md                  # the pipeline diagram, chunking/rerank trade-offs, how to adapt
├── pyproject.toml
├── src/rag_pipeline/
│   ├── __init__.py
│   ├── ingest.py              #   loaders + chunking (size/overlap, structure-aware)
│   ├── embed.py               #   embedding step (mock embeddings default; real optional)
│   ├── stores/
│   │   ├── base.py            #   VectorStore Protocol
│   │   ├── memory.py          #   in-memory store (MOCK default, deterministic)
│   │   └── chroma.py          #   local Chroma adapter (cloud Pinecone noted as the swap)
│   ├── retrieve.py            #   hybrid search (dense + keyword) + fusion
│   └── rerank.py              #   cross-encoder / LLM reranker (mock scorer default)
├── tests/
│   ├── test_chunking.py       #   boundaries, overlap, no-loss
│   ├── test_retrieve.py       #   hybrid beats dense-only on a keyword-y query
│   └── test_rerank.py         #   rerank reorders the shortlist as expected
└── demo.py                    # runnable: ingest a tiny corpus, ask, show ranked hits, MOCK
```

## Composes / depends on
- **`llm-gateway`** — for the embedding call and (optionally) the LLM reranker; the mock
  embedder/scorer keeps the pipeline runnable standalone.
- Otherwise **foundational** for retrieval — solution blueprints depend on it, not vice versa.

## Maps to the book
- **Ch 13 — Retrieval-Augmented Generation:** loaders, chunking, embeddings, vector stores,
  hybrid search, reranking. Makes §13's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-04-building-blocks-of-agents/13-retrieval-augmented-generation/`](../../learn/part-04-building-blocks-of-agents/13-retrieval-augmented-generation/)
  builds chunk→embed→retrieve→rerank as a guided exercise and **ends by pointing here**.

## Maps to the capstone
Standalone version of capstone **`rag/`** — `ingest/` (loaders, chunking, embedding jobs),
`stores/` (Chroma local + Pinecone cloud adapters), and `retrieve.py` (hybrid + rerank).

## Phase-2 definition of done
- [ ] `pytest tests/` passes; chunking, hybrid retrieval, and rerank covered.
- [ ] `python demo.py` ingests a committed tiny corpus and answers in **`MOCK=1`** (deterministic
      embeddings, no API spend).
- [ ] README explains trade-offs: chunk size/overlap, dense-vs-hybrid, when reranking earns its
      latency, and the store-adapter swap (local ↔ cloud).
- [ ] Cross-links (`llm-gateway`, the Ch 13 walkthrough, capstone `rag/`) resolve.
