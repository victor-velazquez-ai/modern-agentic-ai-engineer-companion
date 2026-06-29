"""``rag.stores`` — vector stores behind one adapter interface (Ch 13).

Whether vectors live in process memory, a local Chroma collection, or cloud Pinecone is an
**adapter** decision, not a rewrite. ``base`` defines the :class:`VectorStore` Protocol — the
seam that keeps the retriever ignorant of *where* vectors live. Three implementations ship:

* :class:`InMemoryVectorStore` — pure-Python, deterministic, the MOCK default (and fine for small
  corpora in production).
* :class:`ChromaVectorStore` — local persistence; lazy-imports ``chromadb``.
* :class:`PineconeVectorStore` — managed cloud scale; lazy-imports ``pinecone``.

Swapping local <-> cloud is a one-line construction change; the retriever, reranker, agents, and
API routes never change because they depend only on the Protocol.
"""

from __future__ import annotations

from .base import StoredChunk, VectorStore
from .chroma import ChromaVectorStore
from .memory import InMemoryVectorStore
from .pinecone import PineconeVectorStore

__all__ = [
    "VectorStore",
    "StoredChunk",
    "InMemoryVectorStore",
    "ChromaVectorStore",
    "PineconeVectorStore",
]
