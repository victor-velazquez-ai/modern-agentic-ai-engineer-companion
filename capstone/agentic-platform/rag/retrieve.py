"""Hybrid retrieval + reranking — the door agents and routes depend on (Ch 13).

This module is the seam the rest of the platform sees. Per the build plan: *the ``Retriever``
protocol is the seam — agents and API routes depend on it, never on Chroma directly.* So it
defines:

* :class:`Retriever` — the tiny protocol every caller types against (``retrieve(query, k)``).
* :class:`HybridRetriever` — the production implementation: dense (embedding) + keyword (IDF)
  search over any :class:`~rag.stores.base.VectorStore`, fused with **Reciprocal Rank Fusion**.
* :class:`Reranker` / :class:`MockReranker` — the precision pass that reorders the shortlist
  before it reaches the model.

**Why hybrid.** Dense retrieval nails *meaning* and fumbles *exact terms* (an error code, an
order id, a rare noun); keyword retrieval is the mirror image. Hybrid runs both and fuses them.
**RRF** fuses by *rank*, so the two channels never need a shared score scale (the perennial
headache of weighted blending): ``score = Σ 1/(k + rank)`` across channels. A doc near the top of
*either* list scores well; near the top of *both* wins.

**Why rerank.** Retrieval optimizes *recall* (a wide, cheap net); a reranker optimizes
*precision* — score each shortlisted chunk against the query with a stronger model and reorder, so
the few chunks that land in the prompt are the most relevant. It earns its latency only on a
**short** candidate list (rerank the top ~20-50, never the corpus). The real reranker is an LLM
call through the ``llm/`` gateway; the deterministic :class:`MockReranker` keeps the platform
runnable offline.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .ingest.chunk import Chunk
from .ingest.embed import Embedder, embed_query, get_embedder
from .ingest.tokenize import tokens as _tokens
from .stores.base import StoredChunk, VectorStore

# RRF's smoothing constant. 60 is the value from the original RRF paper (Cormack et al., 2009) and
# the common default; larger flattens the contribution of top ranks.
DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class RetrievalResult:
    """A fused hit: the chunk, its fused score, and the per-channel ranks that produced it.

    Exposing the channel ranks (``dense_rank`` / ``keyword_rank``, 1-based; ``None`` if the chunk
    was absent from that channel's shortlist) lets a reader *see* why hybrid won — and is what the
    reranker, the API's citation rendering, and debugging tools downstream read.
    """

    chunk: Chunk
    score: float
    dense_rank: int | None
    keyword_rank: int | None


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk with its reranker relevance score (higher = more relevant)."""

    chunk: Chunk
    score: float


@runtime_checkable
class Retriever(Protocol):
    """The retrieval seam every caller (agents, ``search_docs`` tool, API routes) types against.

    Depending on this Protocol — not on :class:`HybridRetriever` or a store — is what lets the
    platform swap the store (memory → Chroma → Pinecone) or the retrieval strategy without
    touching the agents or routes.
    """

    def retrieve(self, query: str, *, k: int = ...) -> list[RetrievalResult]:
        ...


@runtime_checkable
class Reranker(Protocol):
    """Anything that reorders retrieval results by query relevance."""

    def rerank(
        self, query: str, results: Sequence[RetrievalResult], *, top_n: int | None = ...
    ) -> list[ScoredChunk]:
        ...


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[StoredChunk]], *, k: int = DEFAULT_RRF_K
) -> dict[str, float]:
    """Fuse several ranked lists into ``{chunk_id: fused_score}`` via RRF.

    Args:
        ranked_lists: each inner list is one channel's hits, already sorted best-first.
        k: RRF smoothing constant (``> 0``).

    Returns:
        A mapping from chunk id to its summed reciprocal-rank score across all channels.

    Raises:
        ValueError: if ``k <= 0``.
    """
    if k <= 0:
        raise ValueError("RRF k must be > 0")
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            fused[hit.chunk.id] = fused.get(hit.chunk.id, 0.0) + 1.0 / (k + rank)
    return fused


class HybridRetriever:
    """Runs dense + keyword search over a store and fuses them with RRF.

    Args:
        store: any :class:`~rag.stores.base.VectorStore`.
        embedder: embedder for the query; defaults to the env-selected one (mock by default), so
            the query is embedded with the *same* model the corpus was.
        rrf_k: RRF smoothing constant.
        candidate_multiplier: how many candidates to pull per channel relative to the final ``k``
            (``fetch = k * multiplier``). A wider shortlist gives fusion (and any reranker) more
            to work with; the cost is a bit more compute.
    """

    def __init__(
        self,
        store: VectorStore,
        *,
        embedder: Embedder | None = None,
        rrf_k: int = DEFAULT_RRF_K,
        candidate_multiplier: int = 4,
    ) -> None:
        self.store = store
        self.embedder = embedder or get_embedder()
        self.rrf_k = rrf_k
        self.candidate_multiplier = max(1, candidate_multiplier)

    def retrieve(
        self, query: str, *, k: int = 5, dense_only: bool = False
    ) -> list[RetrievalResult]:
        """Return the top-``k`` fused hits for ``query``.

        Args:
            k: number of results to return.
            dense_only: if ``True``, skip the keyword channel — the baseline the hybrid path is
                meant to beat (used by the demo's A/B and tests).
        """
        if k <= 0:
            return []
        fetch = k * self.candidate_multiplier

        query_vector = embed_query(query, embedder=self.embedder)
        dense_hits = self.store.search(query_vector, fetch)
        dense_rank = {h.chunk.id: i for i, h in enumerate(dense_hits, start=1)}

        if dense_only:
            keyword_hits: list[StoredChunk] = []
            keyword_rank: dict[str, int] = {}
            fused = reciprocal_rank_fusion([dense_hits], k=self.rrf_k)
        else:
            keyword_hits = self.store.keyword_search(query, fetch)
            keyword_rank = {h.chunk.id: i for i, h in enumerate(keyword_hits, start=1)}
            fused = reciprocal_rank_fusion([dense_hits, keyword_hits], k=self.rrf_k)

        # Index chunks by id once so we can attach the chunk object to each fused id.
        by_id: dict[str, Chunk] = {}
        for h in dense_hits:
            by_id[h.chunk.id] = h.chunk
        for h in keyword_hits:
            by_id.setdefault(h.chunk.id, h.chunk)

        results = [
            RetrievalResult(
                chunk=by_id[cid],
                score=score,
                dense_rank=dense_rank.get(cid),
                keyword_rank=keyword_rank.get(cid),
            )
            for cid, score in fused.items()
        ]
        # Deterministic ordering: fused score desc, ties broken by chunk id.
        results.sort(key=lambda r: (-r.score, r.chunk.id))
        return results[:k]


# A tiny English stopword list. Stripped before lexical reranking so high-frequency function words
# ("how", "do", "my", "the") don't dilute query-term coverage — a real cross-encoder learns to
# ignore them; the mock approximates that with this list.
_STOPWORDS = frozenset(
    """a an and are as at be by do does for from how i in is it its my of on or
    that the this to was what when where which who why with you your me we he she they them
    can could should would will may might""".split()
)


class MockReranker:
    """A deterministic, offline cross-encoder stand-in.

    Score for a (query, chunk) pair combines two lexical signals:

      * **coverage** — fraction of the query's distinct content terms present in the chunk (did
        the chunk address what was asked?), and
      * **density** — query-term hits per ``sqrt(chunk length)`` (is the chunk *about* this, or
        does it just mention it in passing?).

    ``score = coverage + density_weight * density``. Intentionally simple and explainable — a
    teaching/CI stand-in, not a learned cross-encoder — but it produces the right *behavior*:
    among the retriever's shortlist, the chunk that most directly answers the query rises to the
    top, deterministically. The real reranker (LLM through the ``llm/`` gateway) implements the
    same :class:`Reranker` protocol and slots in unchanged.
    """

    def __init__(self, *, density_weight: float = 0.5) -> None:
        self.density_weight = density_weight

    def _score(self, query: str, chunk: Chunk) -> float:
        q_terms = {t for t in _tokens(query) if t not in _STOPWORDS}
        if not q_terms:
            return 0.0
        c_tokens = [t for t in _tokens(chunk.text) if t not in _STOPWORDS]
        if not c_tokens:
            return 0.0
        c_set = set(c_tokens)
        coverage = len(q_terms & c_set) / len(q_terms)
        hits = sum(1 for t in c_tokens if t in q_terms)
        density = hits / math.sqrt(len(c_tokens))
        return coverage + self.density_weight * density

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        *,
        top_n: int | None = None,
    ) -> list[ScoredChunk]:
        """Rescore and reorder ``results`` best-first.

        Args:
            query: the user query.
            results: the retriever's shortlist (already fused).
            top_n: if set, return only the best ``top_n`` after reranking.
        """
        scored = [
            ScoredChunk(chunk=r.chunk, score=self._score(query, r.chunk)) for r in results
        ]
        # Deterministic: score desc, ties broken by chunk id.
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:top_n] if top_n is not None else scored
