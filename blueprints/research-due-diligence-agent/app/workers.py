"""Retrieval/worker agents that gather cited evidence (composes ``rag-pipeline`` + ``agent-loop``).

Each sub-question from the planner is handed to a **retrieval worker**. A worker's whole job is
to gather *evidence*: run hybrid search over the corpus, rerank the shortlist, and return the top
passages **with the source id that grounds each one**. Those source ids are what make the final
brief citable — a passage without a traceable source is worthless for due diligence.

Composition note
----------------
* ``rag-pipeline`` does the retrieval: :class:`HybridRetriever` (dense + keyword, RRF-fused) and
  :class:`MockReranker` (offline cross-encoder stand-in). We import and use them unchanged.
* ``agent-loop`` is the per-worker **tool-use seam**. A worker is conceptually an agent loop with
  a scoped toolset: a ``retrieve_internal`` tool and a ``web_search`` tool. To keep the blueprint
  runnable with zero spend we don't drive a live model loop here; instead the worker calls those
  tools directly and deterministically (the observe→act half of the loop), which is exactly what
  the ``Worker.run`` seam in ``multi-agent-supervisor`` documents. Swapping in a real
  ``agent_loop.AgentLoop(model, tools=...)`` changes nothing the synthesizer sees.

The **stubbed offline "web search"** lives here too: it treats the ``web-*`` source documents as
if they were the open web (decorated with titles/urls from ``data/web_index.json``), so the whole
agent runs with **no network and no API spend**.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import _compose  # noqa: F401 — side effect: puts sibling src/ on sys.path
from .corpus import Corpus

# Imported from sibling rag-pipeline blueprint (NOT forked) — see app/_compose.py.
from rag_pipeline import (  # type: ignore  # noqa: E402
    HybridRetriever,
    MockReranker,
    RetrievalResult,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_WEB_INDEX = _DATA_DIR / "web_index.json"


@dataclass(frozen=True)
class Evidence:
    """One retrieved passage plus the citation that grounds it.

    ``source_id`` is the bracket label that appears next to a claim in the brief; ``snippet`` is
    the supporting text a reflection pass checks the claim against; ``score`` is the reranker's
    relevance score (higher = more on-point). ``doc_type`` / ``url`` carry provenance for the
    source list ("was this internal data-room or open web?").
    """

    source_id: str
    doc_type: str
    title: str
    snippet: str
    score: float
    url: str | None = None

    @property
    def citation(self) -> str:
        """The marker a claim cites — ``[source-id]``."""
        return f"[{self.source_id}]"


def _load_web_index(path: Path = _WEB_INDEX) -> dict[str, dict[str, str]]:
    """Load the stubbed web result metadata (titles/urls), keyed by source id.

    Optional: if the file is missing the worker still runs (urls just come back ``None``).
    """
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["doc_id"]: r for r in data.get("results", [])}


@dataclass
class RetrievalWorker:
    """A scoped retrieval agent: search the corpus, rerank, return cited :class:`Evidence`.

    This is the worker the supervisor delegates a sub-question to. It owns exactly two tools —
    ``retrieve_internal`` (data-room hybrid search) and ``web_search`` (the offline stub) — and
    nothing else; capability confinement is the safety property the supervisor pattern relies on.
    """

    corpus: Corpus
    retriever: HybridRetriever
    reranker: MockReranker = field(default_factory=MockReranker)
    web_index: dict[str, dict[str, str]] = field(default_factory=_load_web_index)
    top_k: int = 6      # how many candidates to retrieve before reranking
    top_n: int = 3      # how many cited passages to keep per sub-question

    # --- the two scoped "tools" ------------------------------------------------------
    def _evidence_from(self, result: RetrievalResult, score: float) -> Evidence:
        """Turn a reranked retrieval hit into a cited :class:`Evidence` row."""
        meta = result.chunk.metadata
        source_id = str(meta.get("doc_id", result.chunk.doc_id))
        doc_type = str(meta.get("doc_type", "web"))
        title = str(meta.get("title", source_id))
        web = self.web_index.get(source_id, {})
        return Evidence(
            source_id=source_id,
            doc_type=doc_type,
            title=str(web.get("title", title)),
            snippet=result.chunk.text,
            score=score,
            url=web.get("url"),
        )

    def gather(self, query: str) -> list[Evidence]:
        """Run retrieve → rerank over the corpus and return the top cited passages.

        This is the observe→act core of the worker's agent loop: it *acts* (searches both the
        internal and web channels via one hybrid index) and *observes* (reranks the shortlist),
        then hands back evidence the synthesizer can cite. Deterministic in MOCK mode.
        """
        # rag-pipeline hybrid retrieval is one index over both internal + web docs; the doc_type
        # metadata on each hit records which channel ("tool") a passage came from.
        results = self.retriever.retrieve(query, k=self.top_k)
        reranked = self.reranker.rerank(query, results, top_n=self.top_n)
        # Map reranked chunks back to their RetrievalResult to keep metadata/provenance.
        by_chunk = {r.chunk.id: r for r in results}
        evidence: list[Evidence] = []
        for scored in reranked:
            result = by_chunk.get(scored.chunk.id)
            if result is None:
                continue
            evidence.append(self._evidence_from(result, scored.score))
        return evidence


def build_retriever(corpus: Corpus, *, candidate_multiplier: int = 4) -> HybridRetriever:
    """Build the rag-pipeline :class:`HybridRetriever` over a loaded corpus.

    Kept as a one-liner factory so the pipeline and the evals construct retrieval the same way.
    """
    return HybridRetriever(corpus.store, candidate_multiplier=candidate_multiplier)


def build_worker(corpus: Corpus, **kwargs: object) -> RetrievalWorker:
    """Construct a :class:`RetrievalWorker` wired to a corpus' retriever (convenience)."""
    return RetrievalWorker(corpus=corpus, retriever=build_retriever(corpus), **kwargs)  # type: ignore[arg-type]
