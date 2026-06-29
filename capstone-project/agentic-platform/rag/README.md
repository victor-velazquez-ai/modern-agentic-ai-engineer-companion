# `rag/` — retrieval over the private corpus

> Capstone subsystem (Appendix C · `rag/`) · realizes book **Ch 13 — Retrieval-Augmented
> Generation** · the assembled counterpart to the [`rag-pipeline`](../../../blueprints/rag-pipeline/)
> blueprint.

The platform's retrieval pipeline: **chunk → embed → retrieve → rerank** over private data, with
the vector store behind an adapter so local ↔ cloud is a one-line swap. It runs **free and offline
by default** (`COMPANION_MOCK=1`): deterministic embeddings, no API spend, no network.

```text
ingest/ ──▶ ┌──────── retrieve.py (hybrid) ────────┐ ──▶ rerank ──▶ top-k to the model
 load        │  dense (cosine)   keyword (IDF)      │    reorder
 chunk       │         └──── RRF fusion ────┘       │
 embed       └────────────── stores/ ───────────────┘
                     memory (default) │ chroma (local) │ pinecone (cloud)
```

## The seam: depend on `Retriever`, never on a store

Agents, the `search_docs` tool, and API routes type against the **`Retriever` protocol**
(`retrieve.py`), not against `HybridRetriever` or any store. That is what lets the platform swap
the store (memory → Chroma → Pinecone) or the strategy without touching a caller:

```python
from rag import Document, chunk_documents, embed_chunks
from rag import InMemoryVectorStore, HybridRetriever, MockReranker

store = InMemoryVectorStore()
store.add(embed_chunks(chunk_documents([Document(id="d1", text="...your corpus...")])))

retriever = HybridRetriever(store)               # satisfies the Retriever protocol
hits = retriever.retrieve("your question", k=5)  # dense + keyword, RRF-fused
answers = MockReranker().rerank("your question", hits)  # precision pass before the model
```

The package has **no required runtime dependencies** — in MOCK mode it imports only the standard
library. Optional integrations (`chromadb`, `pinecone-client`, the `llm/` gateway for real
embeddings) are imported lazily and pulled from the repo-wide `requirements.txt`.

## Layout

| Path | What it does |
|---|---|
| `ingest/loaders.py` | raw sources (string, file, directory) → `Document` with provenance metadata |
| `ingest/chunk.py` | `Document` → overlapping, self-contained `Chunk`s (sliding window or structure-aware); no-loss, stable ids |
| `ingest/embed.py` | `Chunk` → unit-norm vector; `MockEmbedder` by default, real embedder via `llm/` when `MOCK=0` |
| `ingest/tokenize.py` | the one tokenizer every channel shares (so dense/keyword/rerank agree) |
| `stores/base.py` | the `VectorStore` protocol — the store-portability seam |
| `stores/memory.py` | pure-Python in-memory store (MOCK default) + the shared IDF keyword scorer |
| `stores/chroma.py` | local Chroma adapter (persistence); lazy-imports `chromadb` |
| `stores/pinecone.py` | cloud Pinecone adapter (managed scale); lazy-imports `pinecone`, key from env |
| `retrieve.py` | `Retriever`/`HybridRetriever` (dense + keyword, RRF) + `Reranker`/`MockReranker` |

## Store-adapter swap (local ↔ cloud)

All three stores implement the same three methods (`add`, `search`, `keyword_search`) and share
one IDF keyword scorer (`stores/memory.py`), so the keyword channel ranks identically wherever
vectors live. Going to the cloud is a **construction change, not a rewrite**:

```python
from rag import InMemoryVectorStore, ChromaVectorStore, PineconeVectorStore
store = InMemoryVectorStore()                              # tests, small corpora
store = ChromaVectorStore(persist_directory="./chroma")    # local persistence
store = PineconeVectorStore("agentic-platform", namespace=tenant_id)  # cloud, per-tenant
```

The retriever, reranker, agents, and routes do not change a line.

## MOCK vs. live & secrets

- **MOCK by default** (`COMPANION_MOCK=1`): deterministic feature-hashing embedder, IDF keyword
  scorer, heuristic reranker → identical results every run, no API spend, no network.
- **Live** (`COMPANION_MOCK=0`): `get_embedder()` borrows a real embedder from the platform `llm/`
  gateway if it is built and keyed; otherwise it transparently falls back to the mock so nothing
  breaks at import.
- **Secrets from env only.** `CHROMA_URL`, `PINECONE_API_KEY` are read from the environment
  (`.env.example`); nothing is hardcoded, and the Pinecone adapter refuses to construct without
  `PINECONE_API_KEY`.

## Maps to the book

- **Ch 13 — RAG:** loaders, chunking, embeddings, vector stores, hybrid search, reranking.
- **Blueprint:** [`rag-pipeline`](../../../blueprints/rag-pipeline/) is the same pipeline in
  isolation; this is the integrated capstone subsystem the agents and API consume.
