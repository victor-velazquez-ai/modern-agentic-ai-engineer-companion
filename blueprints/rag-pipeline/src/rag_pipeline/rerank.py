"""Reranking — reorder the shortlist before it reaches the model (Ch 13, "Reranking").

Retrieval optimizes for *recall*: cast a wide, cheap net so the right chunk is somewhere in the
top-N. A **reranker** then optimizes for *precision*: score each shortlisted chunk against the
query with a stronger (but more expensive) model and reorder, so the few chunks that actually
land in the prompt are the most relevant. The classic stack is bi-encoder retrieve -> cross-
encoder rerank, or an LLM-as-reranker.

Because rerankers are *quadratic in attention over (query, chunk)* and you pay per pair, they
earn their latency only on a **short** candidate list — rerank the top ~20-50, not the corpus.
That trade-off is the senior judgment this module makes explicit (and the README expands on).

In the book's stack the real reranker is an LLM call through the **llm-gateway**. Here the
default is a deterministic :class:`MockReranker` (no model, no spend) whose score is a blend of
lexical overlap and a coverage term — enough to *reorder a shortlist sensibly* and to make the
PLAN's "rerank reorders the shortlist as expected" test deterministic. The gateway-backed
reranker would implement the same :class:`Reranker` protocol and slot in unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .ingest import Chunk
from .retrieve import RetrievalResult
from .tokenize import tokens as _tokens

# A tiny English stopword list. Stripped before lexical scoring so high-frequency function
# words ("how", "do", "my", "the") don't dilute query-term coverage — a real cross-encoder
# learns to ignore them; the mock approximates that with this list. Small on purpose: it covers
# the words that actually distort short-query scoring without pretending to be a full NLP stack.
_STOPWORDS = frozenset(
    """a an and are as at be by do does for from how i in is it its my of on or
    that the this to was what when where which who why with you your me we he she they them
    can could should would will may might""".split()
)


@dataclass(frozen=True)
class ScoredChunk:
    """A chunk with its reranker relevance score (higher = more relevant)."""

    chunk: Chunk
    score: float


@runtime_checkable
class Reranker(Protocol):
    """Anything that reorders retrieval results by query relevance."""

    def rerank(
        self, query: str, results: Sequence[RetrievalResult], *, top_n: int | None = ...
    ) -> list[ScoredChunk]:
        ...


class MockReranker:
    """A deterministic, offline cross-encoder stand-in.

    Score for a (query, chunk) pair combines two lexical signals:

      * **coverage** — fraction of the query's distinct terms present in the chunk (did the
        chunk address what was asked?), and
      * **density** — query-term hits per ``sqrt(chunk length)`` (is the chunk *about* this, or
        does it just mention it in passing?).

    ``score = coverage + density_weight * density``. This is intentionally simple and explainable
    — it is a teaching/CI stand-in, not a learned cross-encoder — but it produces the right
    *behavior*: among the retriever's shortlist, the chunk that most directly answers the query
    rises to the top, deterministically.
    """

    def __init__(self, *, density_weight: float = 0.5) -> None:
        self.density_weight = density_weight

    def _score(self, query: str, chunk: Chunk) -> float:
        # Score on *content* terms only: drop stopwords from the query so coverage measures
        # whether the chunk addresses the meaningful words asked about.
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
            ScoredChunk(chunk=r.chunk, score=self._score(query, r.chunk))
            for r in results
        ]
        # Deterministic: score desc, ties broken by chunk id.
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:top_n] if top_n is not None else scored
