"""rag_pipeline — a hybrid retrieval pipeline: chunk -> embed -> retrieve -> rerank.

The standalone, hardened version of the capstone ``rag/`` module and the realization of
book **Ch 13 — Retrieval-Augmented Generation**. It is *foundational*: solution blueprints
(customer-support, internal-knowledge, contract-review, incident-response, ...) compose it.

Design goals
------------
- **Runnable with zero API spend by default.** ``COMPANION_MOCK=1`` (the default) uses a
  deterministic hash-based embedder and a heuristic reranker, so the whole pipeline ingests,
  retrieves, and reranks offline and reproducibly.
- **Typed, importable surface.** Stable public objects so the solution blueprints can build on
  it without forking. See ``__all__`` below.
- **Store portability behind an adapter.** ``VectorStore`` is a ``Protocol``; the in-memory
  store is the deterministic default, with a Chroma adapter for local persistence (and a note
  on the cloud Pinecone swap).

Quickstart
----------
>>> from rag_pipeline import Document, chunk_documents, embed_chunks
>>> from rag_pipeline import InMemoryVectorStore, HybridRetriever, MockReranker
>>> store = InMemoryVectorStore()
>>> chunks = chunk_documents([Document(id="d1", text="hybrid search fuses dense and keyword")])
>>> store.add(embed_chunks(chunks))
>>> retriever = HybridRetriever(store)
>>> hits = retriever.retrieve("keyword search", k=3)
>>> reranked = MockReranker().rerank("keyword search", hits)
>>> reranked[0].chunk.text
'hybrid search fuses dense and keyword'
"""

from __future__ import annotations

from .embed import (
    DEFAULT_EMBEDDING_DIM,
    EmbeddedChunk,
    Embedder,
    MockEmbedder,
    embed_chunks,
    embed_query,
    get_embedder,
)
from .ingest import Chunk, Document, chunk_documents, chunk_text
from .rerank import MockReranker, Reranker, ScoredChunk
from .retrieve import HybridRetriever, RetrievalResult, reciprocal_rank_fusion
from .stores.base import StoredChunk, VectorStore
from .stores.chroma import ChromaVectorStore
from .stores.memory import InMemoryVectorStore

__all__ = [
    # ingest
    "Document",
    "Chunk",
    "chunk_text",
    "chunk_documents",
    # embed
    "Embedder",
    "MockEmbedder",
    "EmbeddedChunk",
    "DEFAULT_EMBEDDING_DIM",
    "embed_chunks",
    "embed_query",
    "get_embedder",
    # stores
    "VectorStore",
    "StoredChunk",
    "InMemoryVectorStore",
    "ChromaVectorStore",
    # retrieve
    "HybridRetriever",
    "RetrievalResult",
    "reciprocal_rank_fusion",
    # rerank
    "Reranker",
    "MockReranker",
    "ScoredChunk",
]

__version__ = "0.1.0"
