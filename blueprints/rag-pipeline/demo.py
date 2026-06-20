#!/usr/bin/env python
"""Runnable demo — ingest a tiny corpus, ask, show ranked hits (MOCK by default).

Run it::

    python demo.py                 # offline, deterministic, zero API spend (COMPANION_MOCK=1)
    COMPANION_MOCK=0 python demo.py  # uses the llm-gateway embedder/reranker IF wired in + keyed

What it shows, end to end:
  1. **ingest**  — a handful of in-file "help center" docs -> chunks
  2. **embed**   — chunks -> vectors (deterministic mock embedder by default)
  3. **retrieve**— hybrid (dense + keyword) search, fused with RRF, vs. a dense-only baseline
  4. **rerank**  — reorder the shortlist so the most on-point chunk lands first

The query targets an exact error code so you can *see* the keyword channel and the reranker
earn their keep against semantically-similar distractors.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the package importable from src/ without installation (study & adapt, not a wheel).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rag_pipeline import (  # noqa: E402
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

# A tiny committed corpus designed to show hybrid earning its keep. The answer (kb-001) is keyed
# by a *rare* status code ("QX77", in exactly one doc) plus one *common* term ("gateway"). The
# distractors flood "gateway", so a bag-of-words dense signal ranks them above the answer — and
# the keyword channel, weighting the rare code by IDF, pulls the answer back to the top.
CORPUS = [
    Document(
        id="kb-001",
        text="Status QX77 means the upstream clock drifted; resync time on the gateway "
        "to resolve it.",
        metadata={"source": "help_center", "title": "Status QX77 (clock skew)"},
    ),
    Document(
        id="kb-002",
        text="The gateway gateway gateway proxies requests to the gateway services behind "
        "the gateway tier.",
        metadata={"source": "help_center", "title": "Gateway routing"},
    ),
    Document(
        id="kb-003",
        text="Configure the gateway gateway timeouts and the gateway retry budget in the "
        "gateway settings.",
        metadata={"source": "help_center", "title": "Gateway timeouts"},
    ),
    Document(
        id="kb-004",
        text="Billing invoices and monthly statements are available under the account menu.",
        metadata={"source": "help_center", "title": "Billing"},
    ),
]

QUERY = "QX77 gateway"


def _banner(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    print("Modern Agentic AI Engineer — rag-pipeline blueprint demo")
    print(f"MOCK mode: {'ON (offline, deterministic, $0)' if mock else 'OFF (live)'}")

    # 1) ingest + 2) embed
    chunks = chunk_documents(CORPUS, chunk_size=60, overlap=12)
    store: InMemoryVectorStore = InMemoryVectorStore()
    store.add(embed_chunks(chunks))
    print(f"Ingested {len(CORPUS)} docs -> {len(store)} chunks.")

    retriever = HybridRetriever(store)
    print(f'\nQuery: "{QUERY}"')

    # 3) retrieve — dense-only baseline vs. hybrid
    _banner("Dense-only (baseline)")
    for i, r in enumerate(retriever.retrieve(QUERY, k=3, dense_only=True), 1):
        title = r.chunk.metadata.get("title", r.chunk.doc_id)
        print(f"  {i}. {title:<24} score={r.score:.4f}")

    _banner("Hybrid (dense + keyword, RRF-fused)")
    hybrid = retriever.retrieve(QUERY, k=3)
    for i, r in enumerate(hybrid, 1):
        title = r.chunk.metadata.get("title", r.chunk.doc_id)
        print(
            f"  {i}. {title:<24} score={r.score:.4f} "
            f"(dense_rank={r.dense_rank}, keyword_rank={r.keyword_rank})"
        )

    # 4) rerank the hybrid shortlist
    _banner("After rerank")
    reranked = MockReranker().rerank(QUERY, hybrid, top_n=3)
    for i, s in enumerate(reranked, 1):
        title = s.chunk.metadata.get("title", s.chunk.doc_id)
        print(f"  {i}. {title:<24} rerank_score={s.score:.4f}")

    top = reranked[0]
    print(f'\nTop answer -> "{top.chunk.metadata.get("title", top.chunk.doc_id)}"')
    print(f"  {top.chunk.text}")


if __name__ == "__main__":
    main()
