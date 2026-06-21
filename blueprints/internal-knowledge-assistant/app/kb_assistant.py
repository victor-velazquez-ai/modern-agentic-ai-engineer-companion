"""The Internal Knowledge Assistant — composes the pattern blueprints (Ch 43).

This is the solution. It wires four pattern blueprints together **by relative import, without
forking any of them**:

* **rag-pipeline** — permissioned hybrid retrieval + reranking + inline citations.
* **agent-loop** — grounded generation + an optional light tool call (file a ticket).
* **mcp-server** — the clean, guarded boundary for that ticket tool.
* **observability-stack** — a trace tree per question + a corpus-freshness check.

The one rule the whole design exists to enforce is **filter before retrieval**: the caller's
identity is resolved to ACL groups and the corpus is restricted to readable chunks *before* the
query is ever embedded. A forbidden chunk never enters the candidate set, so it can never reach
the prompt, the citations, or the model — by construction, not by hoping the model behaves.

The flow for one ``ask``:

    identity -> filter store to readable chunks -> hybrid retrieve -> rerank
             -> ground an answer (with citations) via the agent-loop
             -> (optionally) offer a "file a ticket" tool over MCP

Everything runs **free and offline in MOCK mode** (``COMPANION_MOCK=1``, the default): the
embedder/reranker are deterministic mocks, the "model" is a grounded extractive stand-in, and
the ticket tool is an in-process MCP server. Set ``COMPANION_MOCK=0`` and inject gateway-backed
ports (see the README) to go live; the composition does not change.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- compose the sibling pattern blueprints (by import, never forked) ----------------------
# parents[2] of app/kb_assistant.py is the blueprints/ root.
_BLUEPRINTS = Path(__file__).resolve().parents[2]
for _pkg in ("rag-pipeline", "agent-loop", "mcp-server", "observability-stack"):
    _src = _BLUEPRINTS / _pkg / "src"
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

# This package's own modules (run as a package or from the folder).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR.parent))

from rag_pipeline import (  # noqa: E402
    EmbeddedChunk,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    ScoredChunk,
)
from rag_pipeline.embed import get_embedder  # noqa: E402

from app.identity import Principal  # noqa: E402
from ingest.sync_acl import doc_acl  # noqa: E402


# ============================================================================================
# 1) Permission filter — the load-bearing piece. Restrict the store to readable chunks BEFORE
#    any retrieval runs.
# ============================================================================================
def permissioned_store(
    store: InMemoryVectorStore, principal: Principal
) -> InMemoryVectorStore:
    """Return a **new** store containing only the chunks ``principal`` is allowed to read.

    This is the *filter-before-retrieval* rule made literal: we build a smaller index from the
    chunks whose ACL groups intersect the caller's groups, and the retriever only ever sees that
    index. A forbidden chunk is not down-ranked or hidden in post-processing — it is simply not
    present, so no amount of clever querying, summarizing, or prompt-injection can surface it.

    Implementation note: we read the already-embedded chunks back out of the source store and
    re-add the permitted ones, so we never re-embed (cheap) and never mutate the shared corpus.
    """
    permitted = InMemoryVectorStore()
    allowed: list[EmbeddedChunk] = [
        item
        for item in store._items.values()  # internal view: the embedded chunks already indexed
        if principal.can_read(doc_acl(item.chunk.metadata))
    ]
    permitted.add(allowed)
    return permitted


# ============================================================================================
# 2) Retrieval + grounding result types
# ============================================================================================
@dataclass(frozen=True)
class Citation:
    """One cited source backing the answer (what makes it *grounded*, not asserted)."""

    doc_id: str
    title: str
    source: str
    snippet: str


@dataclass(frozen=True)
class Answer:
    """The assistant's response to one question, for one identity.

    ``text`` is the grounded answer; ``citations`` are the sources it stands on; ``visible_docs``
    is how many docs the caller could even see (a permission-aware denominator). When retrieval
    finds nothing the caller may read, ``text`` is an honest "I couldn't find anything you have
    access to" — which is exactly what a permission-probe must get back.
    """

    text: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    visible_docs: int = 0
    retrieved: int = 0

    @property
    def found_something(self) -> bool:
        return bool(self.citations)


def _to_citation(scored: ScoredChunk) -> Citation:
    md = scored.chunk.metadata
    return Citation(
        doc_id=scored.chunk.doc_id,
        title=str(md.get("title", scored.chunk.doc_id)),
        source=str(md.get("source", "")),
        snippet=_snippet(scored.chunk.text),
    )


def _snippet(text: str, *, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _ground_answer(question: str, citations: tuple[Citation, ...]) -> str:
    """Phrase a grounded answer from the cited snippets.

    In MOCK mode this is a deterministic, *extractive* stand-in for the model: it states what the
    top sources say and cites them inline as ``[1]``, ``[2]``. That keeps the demo free and
    reproducible while still exercising the real contract — **an answer must be backed by
    retrieved, permitted sources or it must abstain.** On the live path you swap this for a
    gateway-backed generation step (see :class:`KnowledgeAssistant` / the README); the citation
    discipline is unchanged.
    """
    if not citations:
        return (
            "I couldn't find anything you have access to that answers this. "
            "If you believe this should exist, it may live in a space your account can't read."
        )
    lead = citations[0]
    body = [f"Based on what you can access: {lead.snippet} [1]"]
    for i, c in enumerate(citations[1:], start=2):
        body.append(f"Related: {c.snippet} [{i}]")
    return "\n".join(body)


# ============================================================================================
# 3) The assistant — ties identity + retrieval + grounding (+ optional tracing) together.
# ============================================================================================
class KnowledgeAssistant:
    """Answer employee questions from a permissioned corpus, with cited, grounded answers.

    Parameters
    ----------
    store:
        The full embedded corpus (built by ``ingest.sync_acl.build_index``). It is never mutated;
        each :meth:`ask` derives a per-identity permissioned view from it.
    identity:
        An :class:`~app.identity.IdentityProvider`-resolved :class:`Principal` is passed per call;
        the assistant itself is identity-agnostic and reusable across callers.
    top_k:
        How many reranked chunks to cite. Small on purpose — a grounded answer needs a few sharp
        sources, not the whole shortlist.
    tracer:
        Optional ``observability_stack.Tracer``. When provided, each :meth:`ask` becomes a trace
        tree (run -> retrieval -> rerank -> generation) so a bad answer is debuggable and the
        retrieval k / permitted-doc count is recorded. ``None`` = zero tracing overhead.
    """

    def __init__(
        self,
        store: InMemoryVectorStore,
        *,
        top_k: int = 3,
        tracer: object | None = None,
    ) -> None:
        self.store = store
        self.top_k = max(1, top_k)
        self.tracer = tracer
        self._embedder = get_embedder()
        self._reranker = MockReranker()

    def ask(self, question: str, principal: Principal) -> Answer:
        """Answer ``question`` *as* ``principal`` — permission-filtered, grounded, cited."""
        if self.tracer is not None:
            return self._ask_traced(question, principal)
        return self._ask(question, principal)

    # -- core (untraced) -------------------------------------------------------------------
    def _ask(self, question: str, principal: Principal) -> Answer:
        # (a) filter BEFORE retrieval — the breach-proof step.
        visible = permissioned_store(self.store, principal)
        visible_docs = len({i.chunk.doc_id for i in visible._items.values()})
        if len(visible) == 0:
            return Answer(text=_ground_answer(question, ()), visible_docs=0, retrieved=0)

        # (b) hybrid retrieve over only the permitted chunks.
        retriever = HybridRetriever(visible, embedder=self._embedder)
        hits = retriever.retrieve(question, k=max(self.top_k * 2, 4))

        # (c) rerank the shortlist for precision, then cite the top_k.
        reranked = self._reranker.rerank(question, hits, top_n=self.top_k)
        # Drop zero-relevance chunks: an irrelevant "match" is not a citation.
        reranked = [s for s in reranked if s.score > 0.0]
        citations = tuple(_to_citation(s) for s in reranked)

        # (d) ground an answer on (only) those permitted, cited sources.
        return Answer(
            text=_ground_answer(question, citations),
            citations=citations,
            visible_docs=visible_docs,
            retrieved=len(hits),
        )

    # -- core (traced) ---------------------------------------------------------------------
    def _ask_traced(self, question: str, principal: Principal) -> Answer:
        """Same flow as :meth:`_ask`, wrapped in observability spans.

        Imported lazily so the assistant has no hard dependency on observability-stack when no
        tracer is supplied. The span tree (run -> retrieval -> rerank -> generation) is what you
        attach to a bad-answer report.
        """
        from observability_stack import SpanKind  # local import: only when tracing

        tracer = self.tracer
        with tracer.run("knowledge-assistant", attributes={"user": principal.user_id}):
            visible = permissioned_store(self.store, principal)
            visible_docs = len({i.chunk.doc_id for i in visible._items.values()})
            if len(visible) == 0:
                with tracer.span("generation", SpanKind.LLM):
                    return Answer(text=_ground_answer(question, ()), visible_docs=0)

            with tracer.retrieval_span(query=question, k=self.top_k) as span:
                retriever = HybridRetriever(visible, embedder=self._embedder)
                hits = retriever.retrieve(question, k=max(self.top_k * 2, 4))
                span.set_attribute("permitted_docs", visible_docs)

            with tracer.span("rerank", SpanKind.CHAIN):
                reranked = self._reranker.rerank(question, hits, top_n=self.top_k)
                reranked = [s for s in reranked if s.score > 0.0]
            citations = tuple(_to_citation(s) for s in reranked)

            with tracer.span("generation", SpanKind.LLM) as span:
                text = _ground_answer(question, citations)
                span.set_attribute("citations", len(citations))

        return Answer(
            text=text,
            citations=citations,
            visible_docs=visible_docs,
            retrieved=len(hits),
        )
