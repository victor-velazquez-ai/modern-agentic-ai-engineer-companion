"""``rag`` — the platform's retrieval subsystem (Appendix C · ``rag/``).

This is the capstone's *assembled* retrieval pipeline — the integrated counterpart to the
``rag-pipeline`` blueprint. Where the blueprint shows the chunk → embed → retrieve → rerank
mechanism in isolation, this is how it wires into the wider platform: agents and API routes
depend on the :class:`~rag.retrieve.Retriever` protocol (the seam), never on Chroma or Pinecone
directly, so swapping the local store for the cloud one is a one-line construction change.

Layout (matches Appendix C)
---------------------------
``ingest/``     loaders (raw bytes/files → :class:`Document`), chunking, and the embedding job.
``stores/``     the :class:`VectorStore` protocol + Chroma (local) and Pinecone (cloud) adapters,
                with a pure-Python in-memory store as the deterministic MOCK default.
``retrieve.py`` hybrid search (dense + keyword, fused with RRF) and a reranker precision pass.

Everything is MOCK-runnable: with ``COMPANION_MOCK=1`` (the default) the whole pipeline ingests,
embeds, retrieves, and reranks **offline, deterministically, with zero API keys and zero spend**.
The single seam to a real model is :func:`~rag.ingest.embed.get_embedder`, which borrows a real
embedder from the platform ``llm/`` gateway when ``COMPANION_MOCK=0`` and a key is present, and
transparently falls back to the deterministic mock otherwise. Secrets are read from the
environment only.

Quickstart
----------
>>> from rag import Document, chunk_documents, embed_chunks
>>> from rag import InMemoryVectorStore, HybridRetriever, MockReranker
>>> store = InMemoryVectorStore()
>>> chunks = chunk_documents([Document(id="d1", text="hybrid search fuses dense and keyword")])
>>> store.add(embed_chunks(chunks))
>>> hits = HybridRetriever(store).retrieve("keyword search", k=3)
>>> MockReranker().rerank("keyword search", hits)[0].chunk.text
'hybrid search fuses dense and keyword'
"""

from __future__ import annotations

from .ingest import (
    DEFAULT_EMBEDDING_DIM,
    Chunk,
    Document,
    EmbeddedChunk,
    Embedder,
    MockEmbedder,
    chunk_documents,
    chunk_text,
    embed_chunks,
    embed_query,
    get_embedder,
    load_directory,
    load_documents,
    load_text,
)
from .retrieve import (
    HybridRetriever,
    MockReranker,
    Reranker,
    Retriever,
    RetrievalResult,
    ScoredChunk,
    reciprocal_rank_fusion,
)
from .stores import (
    ChromaVectorStore,
    InMemoryVectorStore,
    PineconeVectorStore,
    StoredChunk,
    VectorStore,
)

__all__ = [
    # ingest — loaders
    "Document",
    "load_text",
    "load_documents",
    "load_directory",
    # ingest — chunking
    "Chunk",
    "chunk_text",
    "chunk_documents",
    # ingest — embedding
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
    "PineconeVectorStore",
    # retrieve + rerank
    "Retriever",
    "HybridRetriever",
    "RetrievalResult",
    "reciprocal_rank_fusion",
    "Reranker",
    "MockReranker",
    "ScoredChunk",
]

__version__ = "0.1.0"
