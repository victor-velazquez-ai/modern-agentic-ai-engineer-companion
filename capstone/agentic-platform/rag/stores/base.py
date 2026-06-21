"""The ``VectorStore`` Protocol — store portability as a typed seam (Ch 13).

Whether vectors live in process memory, a local Chroma collection, or cloud Pinecone is an
**adapter** decision. Every store implements this one tiny interface and the retriever depends
only on it. Swapping local <-> cloud is then a one-line construction change, not a rewrite.

The keyword side of hybrid search also lives behind this Protocol (:meth:`keyword_search`), so a
store backed by a real search engine (a Chroma full-text index, a Pinecone sparse index, or a
BM25 service) can serve it natively instead of the in-memory default's term-overlap scorer.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..ingest.chunk import Chunk
from ..ingest.embed import EmbeddedChunk


@dataclass(frozen=True)
class StoredChunk:
    """A retrieval hit: the chunk plus the score that surfaced it.

    ``score`` is interpreted per channel — cosine similarity for :meth:`VectorStore.search`, a
    keyword-overlap score for :meth:`VectorStore.keyword_search`. Fusion (see
    :func:`rag.retrieve.reciprocal_rank_fusion`) consumes *ranks*, not raw scores, so the two
    channels never need a shared scale.
    """

    chunk: Chunk
    score: float


@runtime_checkable
class VectorStore(Protocol):
    """The minimal surface every store adapter implements."""

    def add(self, embedded: Sequence[EmbeddedChunk]) -> None:
        """Upsert embedded chunks. Re-adding a chunk id replaces it (idempotent ingest)."""
        ...

    def search(self, query_vector: Sequence[float], k: int) -> list[StoredChunk]:
        """Dense search: the ``k`` nearest chunks to ``query_vector`` by cosine similarity."""
        ...

    def keyword_search(self, query: str, k: int) -> list[StoredChunk]:
        """Sparse/keyword search: the ``k`` chunks with the strongest term overlap with
        ``query``. Backs the keyword half of hybrid retrieval."""
        ...

    def __len__(self) -> int:
        """Number of chunks currently stored."""
        ...
