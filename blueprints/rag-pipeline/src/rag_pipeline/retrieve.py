"""Hybrid search — dense + keyword, fused (Ch 13, "Hybrid search").

Dense (embedding) retrieval is great at *meaning* and weak at *exact terms*: a query for an
error code, an order id, or a rare proper noun can rank below a fuzzy paraphrase. Keyword
retrieval is the mirror image. **Hybrid search runs both and fuses the rankings** so you get the
union of their strengths.

Fusion here is **Reciprocal Rank Fusion (RRF)** — the senior default because it needs no score
calibration between channels. Cosine similarities and keyword-overlap scores live on different,
incomparable scales; trying to add them means tuning weights forever. RRF instead combines
*ranks*: a chunk's fused score is ``sum over channels of 1 / (k_rrf + rank)``. A document that is
near the top of *either* list scores well; a document near the top of *both* wins. It is robust,
parameter-light (one constant), and exactly the behavior the PLAN's test asserts: a keyword-y
query where the right answer is lexically obvious must beat dense-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .embed import Embedder, embed_query, get_embedder
from .ingest import Chunk
from .stores.base import StoredChunk, VectorStore

# RRF's smoothing constant. 60 is the value from the original RRF paper (Cormack et al., 2009)
# and the common default; larger flattens the contribution of top ranks.
DEFAULT_RRF_K = 60


@dataclass(frozen=True)
class RetrievalResult:
    """A fused hit: the chunk, its fused score, and the per-channel ranks that produced it.

    Exposing the channel ranks (``dense_rank`` / ``keyword_rank``, 1-based; ``None`` if the
    chunk was absent from that channel's shortlist) is what lets a reader *see* why hybrid won —
    and what the reranker and debugging tools downstream read.
    """

    chunk: Chunk
    score: float
    dense_rank: int | None
    keyword_rank: int | None


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[StoredChunk]], *, k: int = DEFAULT_RRF_K
) -> dict[str, float]:
    """Fuse several ranked lists into ``{chunk_id: fused_score}`` via RRF.

    Args:
        ranked_lists: Each inner list is one channel's hits, already sorted best-first.
        k: RRF smoothing constant (``> 0``).

    Returns:
        A mapping from chunk id to its summed reciprocal-rank score across all channels.
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
        store: any :class:`~rag_pipeline.stores.base.VectorStore`.
        embedder: embedder for the query; defaults to the env-selected one (mock by default), so
            the query is embedded with the *same* model the corpus was.
        rrf_k: RRF smoothing constant.
        candidate_multiplier: how many candidates to pull per channel relative to the final
            ``k`` (``fetch = k * multiplier``). A wider shortlist gives fusion (and any reranker)
            more to work with; the cost is a bit more compute.
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
                meant to beat (used by the PLAN's test and the demo's A/B).
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
            fused = reciprocal_rank_fusion(
                [dense_hits, keyword_hits], k=self.rrf_k
            )

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
