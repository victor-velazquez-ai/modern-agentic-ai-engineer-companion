"""In-memory vector store — the deterministic MOCK default (no deps, no network).

This is the store the pipeline uses out of the box. It holds every embedded chunk in a list and
computes cosine similarity in pure Python, so it is exact, reproducible, and dependency-free.
That makes it ideal for tests, CI, notebooks, and reading the pipeline *by running it* — and a
perfectly reasonable choice for small corpora (a few thousand chunks) in production.

For the keyword channel it uses an **IDF-weighted term-overlap** score — the heart of BM25's
ranking signal, kept minimal. A query term contributes ``idf(term)`` to a chunk's score, where
``idf`` is high for *rare* terms (an error code that appears in one chunk) and low for *common*
ones (words in every chunk). That is exactly why hybrid search beats dense-only on keyword-y
queries: a rare exact term (an ID, an error code, a SKU) dominates the keyword score and pulls
the chunk that contains it to the top, even when dense embeddings smear it among look-alikes.
"""

from __future__ import annotations

import math
from typing import Sequence

from ..embed import EmbeddedChunk
from ..tokenize import tokens as _tokenize
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


def _tokens(text: str) -> set[str]:
    return set(_tokenize(text))


class InMemoryVectorStore:
    """A pure-Python :class:`~rag_pipeline.stores.base.VectorStore`."""

    def __init__(self) -> None:
        # Keyed by chunk id for idempotent upsert; insertion order is preserved (py3.7+).
        self._items: dict[str, EmbeddedChunk] = {}

    def add(self, embedded: Sequence[EmbeddedChunk]) -> None:
        for item in embedded:
            self._items[item.chunk.id] = item

    def search(
        self, query_vector: Sequence[float], k: int
    ) -> list[StoredChunk]:
        if k <= 0:
            return []
        scored = [
            StoredChunk(chunk=item.chunk, score=_cosine(query_vector, item.vector))
            for item in self._items.values()
        ]
        # Stable: ties break on chunk id so results are reproducible across runs.
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    def _idf(self) -> dict[str, float]:
        """Inverse document frequency per term over the current corpus.

        ``idf(t) = ln((N - df + 0.5) / (df + 0.5) + 1)`` — the BM25 IDF form, which is large for
        rare terms and near zero for terms in (almost) every chunk. Computed on demand; corpora
        here are small and the keyword path is not hot. A persistent store would cache this.
        """
        n = len(self._items)
        df: dict[str, int] = {}
        for item in self._items.values():
            for term in _tokens(item.chunk.text):
                df[term] = df.get(term, 0) + 1
        return {
            term: math.log((n - d + 0.5) / (d + 0.5) + 1.0) for term, d in df.items()
        }

    def keyword_search(self, query: str, k: int) -> list[StoredChunk]:
        if k <= 0:
            return []
        q_tokens = _tokens(query)
        if not q_tokens:
            return []
        idf = self._idf()
        scored: list[StoredChunk] = []
        for item in self._items.values():
            c_tokens = _tokens(item.chunk.text)
            if not c_tokens:
                continue
            shared = q_tokens & c_tokens
            if not shared:
                continue
            # Sum IDF of matched query terms, length-normalized so a long chunk that merely
            # mentions a rare term in passing doesn't outrank a focused one.
            score = sum(idf.get(t, 0.0) for t in shared) / math.sqrt(len(c_tokens))
            if score <= 0.0:
                continue
            scored.append(StoredChunk(chunk=item.chunk, score=score))
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)
