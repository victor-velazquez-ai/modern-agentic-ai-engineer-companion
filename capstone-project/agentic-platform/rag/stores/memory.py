"""In-memory vector store — the deterministic MOCK default (no deps, no network).

This is the store the pipeline uses out of the box. It holds every embedded chunk in a dict and
computes cosine similarity in pure Python, so it is exact, reproducible, and dependency-free.
That makes it ideal for tests, CI, notebooks, and reading the pipeline *by running it* — and a
perfectly reasonable choice for small corpora (a few thousand chunks) in production.

For the keyword channel it uses an **IDF-weighted term-overlap** score — the heart of BM25's
ranking signal, kept minimal. A query term contributes ``idf(term)`` to a chunk's score, where
``idf`` is high for *rare* terms (an error code that appears in one chunk) and low for *common*
ones. That is exactly why hybrid search beats dense-only on keyword-y queries: a rare exact term
(an ID, an error code, a SKU) dominates the keyword score and pulls the chunk that contains it to
the top, even when dense embeddings smear it among look-alikes.

The IDF scorer (:func:`idf_table`, :func:`keyword_score`) is exported so the Chroma and Pinecone
adapters can reuse the identical lexical signal — the three stores then rank the keyword channel
the same way, and a swap never changes behavior.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from ..ingest.chunk import Chunk
from ..ingest.embed import EmbeddedChunk
from ..ingest.tokenize import tokens as _tokenize
from .base import StoredChunk


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity. Vectors from the embedder are unit-norm, but we normalize defensively
    so an externally supplied (non-normalized) query vector still scores correctly."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _term_set(text: str) -> set[str]:
    return set(_tokenize(text))


def idf_table(texts: Sequence[str]) -> dict[str, float]:
    """Inverse document frequency per term over ``texts``.

    ``idf(t) = ln((N - df + 0.5) / (df + 0.5) + 1)`` — the BM25 IDF form, which is large for rare
    terms and near zero for terms in (almost) every chunk. Shared by all store adapters so the
    keyword channel ranks identically wherever vectors live.
    """
    n = len(texts)
    df: dict[str, int] = {}
    for text in texts:
        for term in _term_set(text):
            df[term] = df.get(term, 0) + 1
    return {term: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for term, d in df.items()}


def keyword_score(query_tokens: set[str], chunk_text: str, idf: Mapping[str, float]) -> float:
    """Length-normalized, IDF-weighted overlap score for one chunk against a query.

    Sums the IDF of matched query terms, then divides by ``sqrt(chunk length)`` so a long chunk
    that merely mentions a rare term in passing does not outrank a focused one. Returns ``0.0``
    when there is no overlap.
    """
    c_tokens = _tokenize(chunk_text)
    if not c_tokens or not query_tokens:
        return 0.0
    shared = query_tokens & set(c_tokens)
    if not shared:
        return 0.0
    return sum(idf.get(t, 0.0) for t in shared) / math.sqrt(len(c_tokens))


class InMemoryVectorStore:
    """A pure-Python :class:`~rag.stores.base.VectorStore`."""

    def __init__(self) -> None:
        # Keyed by chunk id for idempotent upsert; insertion order is preserved (py3.7+).
        self._items: dict[str, EmbeddedChunk] = {}

    def add(self, embedded: Sequence[EmbeddedChunk]) -> None:
        for item in embedded:
            self._items[item.chunk.id] = item

    def search(self, query_vector: Sequence[float], k: int) -> list[StoredChunk]:
        if k <= 0:
            return []
        scored = [
            StoredChunk(chunk=item.chunk, score=_cosine(query_vector, item.vector))
            for item in self._items.values()
        ]
        # Stable: ties break on chunk id so results are reproducible across runs.
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    def keyword_search(self, query: str, k: int) -> list[StoredChunk]:
        if k <= 0:
            return []
        q_tokens = _term_set(query)
        if not q_tokens:
            return []
        idf = idf_table([item.chunk.text for item in self._items.values()])
        scored: list[StoredChunk] = []
        for item in self._items.values():
            score = keyword_score(q_tokens, item.chunk.text, idf)
            if score <= 0.0:
                continue
            scored.append(StoredChunk(chunk=item.chunk, score=score))
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)
