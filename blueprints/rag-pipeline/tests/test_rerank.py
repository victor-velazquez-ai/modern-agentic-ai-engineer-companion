"""Rerank tests — rerank reorders the shortlist as expected (PLAN: test_rerank.py)."""

from __future__ import annotations

from rag_pipeline import (
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)
from rag_pipeline.ingest import Chunk
from rag_pipeline.retrieve import RetrievalResult


def _result(cid: str, text: str, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(id=cid, doc_id=cid, text=text, index=0),
        score=score,
        dense_rank=None,
        keyword_rank=None,
    )


def test_rerank_promotes_the_directly_relevant_chunk() -> None:
    # The retriever (by fused score) puts a weak, passing-mention chunk on top; the reranker,
    # scoring (query, chunk) directly, must reorder so the chunk that actually answers wins.
    query = "how to rotate an expired credential"
    results = [
        # Highest retrieval score, but only tangentially about the query.
        _result("weak", "An overview of authentication concepts and terminology.", 0.90),
        # Lower retrieval score, but directly answers — high query-term coverage + density.
        _result(
            "strong",
            "To rotate an expired credential, revoke the old token and issue a new one.",
            0.40,
        ),
    ]
    reranked = MockReranker().rerank(query, results)
    assert reranked[0].chunk.id == "strong"  # reranker overrides the retrieval order
    assert reranked[0].score > reranked[1].score


def test_rerank_is_deterministic() -> None:
    query = "vector store adapter swap"
    results = [
        _result("a", "swapping the vector store adapter from local to cloud", 0.5),
        _result("b", "an unrelated note about chunk overlap sizing", 0.5),
        _result("c", "the vector store adapter swap is a one-line change", 0.5),
    ]
    rr = MockReranker()
    first = [s.chunk.id for s in rr.rerank(query, results)]
    second = [s.chunk.id for s in rr.rerank(query, results)]
    assert first == second


def test_rerank_top_n_truncates() -> None:
    query = "alpha"
    results = [_result(f"d{i}", f"alpha text {i}", 0.5) for i in range(5)]
    reranked = MockReranker().rerank(query, results, top_n=2)
    assert len(reranked) == 2


def test_rerank_preserves_shortlist_membership() -> None:
    query = "retrieval"
    results = [_result(f"d{i}", f"retrieval doc {i}", 0.5 - i * 0.01) for i in range(4)]
    reranked = MockReranker().rerank(query, results)
    assert {s.chunk.id for s in reranked} == {r.chunk.id for r in results}


def test_rerank_after_retrieval_end_to_end() -> None:
    docs = [
        Document(id="ans", text="To reset a forgotten password, open settings and click reset."),
        Document(id="noise1", text="A history of password security and hashing algorithms."),
        Document(id="noise2", text="Settings let you change your theme, language, and timezone."),
    ]
    store = InMemoryVectorStore()
    store.add(embed_chunks(chunk_documents(docs, chunk_size=60, overlap=10)))
    retriever = HybridRetriever(store)
    query = "how do I reset my password"

    shortlist = retriever.retrieve(query, k=3)
    reranked = MockReranker().rerank(query, shortlist, top_n=3)
    assert reranked[0].chunk.doc_id == "ans"


def test_empty_query_scores_zero() -> None:
    results = [_result("a", "some content here", 0.5)]
    reranked = MockReranker().rerank("", results)
    assert reranked[0].score == 0.0
