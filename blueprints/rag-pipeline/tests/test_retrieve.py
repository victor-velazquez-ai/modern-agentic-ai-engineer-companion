"""Retrieval tests — hybrid beats dense-only on a keyword-y query (PLAN: test_retrieve.py)."""

from __future__ import annotations

from rag_pipeline import (
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    chunk_documents,
    embed_chunks,
    reciprocal_rank_fusion,
)
from rag_pipeline.stores.base import StoredChunk


def _build_store(docs: list[Document]) -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    store.add(embed_chunks(chunk_documents(docs, chunk_size=60, overlap=10)))
    return store


def test_dense_search_returns_nearest() -> None:
    docs = [
        Document(id="d1", text="cats are small domestic felines that purr"),
        Document(id="d2", text="the stock market fell sharply on tuesday"),
    ]
    store = _build_store(docs)
    retriever = HybridRetriever(store)
    hits = retriever.retrieve("domestic feline pet", k=1)
    assert hits[0].chunk.doc_id == "d1"


def test_hybrid_beats_dense_only_on_keyword_query() -> None:
    # The PLAN's headline assertion. The right answer is keyed by a *rare* token ("QX77", a
    # status code present in exactly one doc) plus one *common* term ("gateway"). The distractors
    # flood the common term, so a bag-of-words dense signal ranks them above the answer. The
    # keyword channel weights the rare token by IDF and ranks the answer first, so RRF fusion
    # pulls it up — hybrid ranks the answer strictly higher than dense-only does.
    docs = [
        Document(
            id="correct",
            text="Status QX77 means the upstream clock drifted; resync time on the gateway "
            "to resolve it.",
        ),
        Document(
            id="distract1",
            text="The gateway gateway gateway proxies requests to the gateway services behind "
            "the gateway.",
        ),
        Document(
            id="distract2",
            text="Configure the gateway gateway timeouts and the gateway retry budget in the "
            "gateway settings.",
        ),
        Document(id="filler", text="Unrelated note about billing invoices and monthly statements."),
    ]
    store = _build_store(docs)
    retriever = HybridRetriever(store)
    query = "QX77 gateway"

    dense_only = retriever.retrieve(query, k=4, dense_only=True)
    hybrid = retriever.retrieve(query, k=4)

    def rank_of(results: list, doc_id: str) -> int:
        for i, r in enumerate(results):
            if r.chunk.doc_id == doc_id:
                return i
        return len(results)

    dense_rank = rank_of(dense_only, "correct")
    hybrid_rank = rank_of(hybrid, "correct")

    # Dense-only is fooled by the common-term flood: the answer is NOT first.
    assert dense_rank > 0
    # The keyword channel ranks the answer first on the rare, high-IDF term...
    kw_only = store.keyword_search(query, 4)
    assert kw_only[0].chunk.doc_id == "correct"
    # ...so fusion lifts the answer strictly higher than dense-only put it, into the top of
    # the hybrid list.
    assert hybrid_rank < dense_rank
    assert hybrid_rank <= 1


def test_keyword_channel_alone_finds_exact_term() -> None:
    docs = [
        Document(id="correct", text="The retry budget for error E1492 is three attempts."),
        Document(id="other", text="General guidance on retries and exponential backoff."),
    ]
    store = _build_store(docs)
    hits = store.keyword_search("E1492", k=5)
    assert hits
    assert hits[0].chunk.doc_id == "correct"


def test_retrieval_is_deterministic() -> None:
    docs = [Document(id=f"d{i}", text=f"document number {i} about topic {i}") for i in range(8)]
    store = _build_store(docs)
    retriever = HybridRetriever(store)
    first = [r.chunk.id for r in retriever.retrieve("topic 3 document", k=5)]
    second = [r.chunk.id for r in retriever.retrieve("topic 3 document", k=5)]
    assert first == second  # stable ordering across calls


def test_results_carry_channel_ranks() -> None:
    docs = [
        Document(id="d1", text="alpha beta gamma keyword-term delta"),
        Document(id="d2", text="epsilon zeta eta theta iota"),
    ]
    store = _build_store(docs)
    retriever = HybridRetriever(store)
    results = retriever.retrieve("keyword-term", k=2)
    top = results[0]
    # The winning chunk appears in at least one channel's shortlist.
    assert (top.dense_rank is not None) or (top.keyword_rank is not None)
    assert top.keyword_rank is not None  # exact term -> present in keyword channel


def test_rrf_combines_ranks() -> None:
    # A doc ranked #1 in both channels must outscore a doc ranked #1 in only one.
    from rag_pipeline.ingest import Chunk

    def hit(cid: str) -> StoredChunk:
        return StoredChunk(chunk=Chunk(id=cid, doc_id=cid, text=cid, index=0), score=1.0)

    dense = [hit("both"), hit("dense_only")]
    keyword = [hit("both"), hit("kw_only")]
    fused = reciprocal_rank_fusion([dense, keyword], k=60)
    assert fused["both"] > fused["dense_only"]
    assert fused["both"] > fused["kw_only"]


def test_empty_k_returns_nothing() -> None:
    store = _build_store([Document(id="d1", text="anything at all here")])
    retriever = HybridRetriever(store)
    assert retriever.retrieve("anything", k=0) == []
