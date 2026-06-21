"""Cloud Pinecone adapter — the managed-scale swap (Ch 13).

The third position on the one :class:`~rag.stores.base.VectorStore` interface: a managed cloud
index for corpora past what a single box holds, durable across instances. Going from local Chroma
to cloud Pinecone is **another adapter, not a rewrite** — ``add → upsert``, ``search → query`` —
and the retriever, reranker, agents, and API routes do not change a line. That is the whole point
of the Protocol.

**Import-safety + secrets.** ``pinecone`` is an optional dependency (in ``requirements.txt``, not
needed for the default MOCK path), so it is imported *lazily inside ``__init__``* and this module
imports with zero third-party deps. The API key is read from the ``PINECONE_API_KEY`` environment
variable only — never an argument, never hardcoded — matching the platform's "secrets from env"
rule.

**The keyword channel.** Pinecone is a dense ANN index; it has no built-in BM25. We keep behavior
identical to the other stores by pulling the candidate documents' text from the returned metadata
and applying the shared IDF scorer (:func:`rag.stores.memory.keyword_score`). A production build
would instead use a Pinecone *sparse* index (or a sidecar BM25 service) for true server-side
keyword search; the :class:`~rag.stores.base.VectorStore` surface is unchanged either way.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from ..ingest.embed import EmbeddedChunk
from .base import StoredChunk
from .memory import _term_set, idf_table, keyword_score

_INSTALL_HINT = (
    "PineconeVectorStore requires the optional 'pinecone' package. Install it with "
    "`pip install pinecone-client` (it is listed in requirements.txt). The default in-memory "
    "store needs no extra dependencies — use InMemoryVectorStore for MOCK/offline runs."
)
_KEY_HINT = (
    "PineconeVectorStore needs PINECONE_API_KEY in the environment (see .env.example). Secrets "
    "are read from the environment only — never pass the key as an argument."
)

# Pinecone caps how many vectors metadata-filtered queries can return per call; the keyword
# channel scans a bounded candidate pool rather than the whole index (which a real sparse index
# would handle server-side).
_KEYWORD_CANDIDATE_POOL = 1000


class PineconeVectorStore:
    """A :class:`~rag.stores.base.VectorStore` backed by a managed Pinecone index.

    Args:
        index_name: the Pinecone index to use (must already exist, or be created out of band by
            the ingestion job / infra; this adapter does not provision indexes).
        namespace: logical partition within the index — the platform uses one namespace per
            tenant so a query never crosses tenant boundaries.
        dimension: embedding dimension, used only to validate vectors before upsert.

    Raises:
        RuntimeError: if ``pinecone`` is not installed or ``PINECONE_API_KEY`` is unset.
    """

    def __init__(
        self,
        index_name: str = "agentic-platform",
        *,
        namespace: str = "default",
        dimension: int | None = None,
    ) -> None:
        try:
            from pinecone import Pinecone  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only without pinecone.
            raise RuntimeError(_INSTALL_HINT) from exc

        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise RuntimeError(_KEY_HINT)

        client = Pinecone(api_key=api_key)
        self._index = client.Index(index_name)
        self._namespace = namespace
        self._dimension = dimension

    def add(self, embedded: Sequence[EmbeddedChunk]) -> None:
        if not embedded:
            return
        vectors = []
        for e in embedded:
            if self._dimension is not None and len(e.vector) != self._dimension:
                raise ValueError(
                    f"vector dim {len(e.vector)} != index dim {self._dimension} for {e.chunk.id}"
                )
            vectors.append(
                {
                    "id": e.chunk.id,
                    "values": list(e.vector),
                    # store the text + provenance so search results can be reconstructed and the
                    # keyword channel has document text to score.
                    "metadata": {
                        "text": e.chunk.text,
                        "doc_id": e.chunk.doc_id,
                        "index": e.chunk.index,
                        **{k: v for k, v in e.chunk.metadata.items()},
                    },
                }
            )
        self._index.upsert(vectors=vectors, namespace=self._namespace)

    def search(self, query_vector: Sequence[float], k: int) -> list[StoredChunk]:
        if k <= 0:
            return []
        result = self._index.query(
            vector=list(query_vector),
            top_k=k,
            namespace=self._namespace,
            include_metadata=True,
            include_values=False,
        )
        hits: list[StoredChunk] = []
        for match in self._matches(result):
            chunk = self._chunk_from_match(match)
            # Pinecone cosine ``score`` is already a similarity in [-1, 1]; pass it through.
            hits.append(StoredChunk(chunk=chunk, score=float(self._match_get(match, "score", 0.0))))
        return hits

    def keyword_search(self, query: str, k: int) -> list[StoredChunk]:
        if k <= 0:
            return []
        q_tokens = _term_set(query)
        if not q_tokens:
            return []
        # No server-side BM25: pull a bounded candidate pool (a zero query returns by id order on
        # most tiers) and rank with the shared IDF scorer so behavior matches the other stores.
        zero = [0.0] * (self._dimension or 1)
        result = self._index.query(
            vector=zero,
            top_k=_KEYWORD_CANDIDATE_POOL,
            namespace=self._namespace,
            include_metadata=True,
            include_values=False,
        )
        candidates = [self._chunk_from_match(m) for m in self._matches(result)]
        idf = idf_table([c.text for c in candidates])
        scored: list[StoredChunk] = []
        for chunk in candidates:
            score = keyword_score(q_tokens, chunk.text, idf)
            if score <= 0.0:
                continue
            scored.append(StoredChunk(chunk=chunk, score=score))
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    # -- helpers: tolerate both dict-like and object-like Pinecone SDK responses ----------------

    @staticmethod
    def _matches(result: object) -> list[object]:
        if isinstance(result, dict):
            return list(result.get("matches", []))
        return list(getattr(result, "matches", []) or [])

    @staticmethod
    def _match_get(match: object, key: str, default: object = None) -> object:
        if isinstance(match, dict):
            return match.get(key, default)
        return getattr(match, key, default)

    def _chunk_from_match(self, match: object):
        from ..ingest.chunk import Chunk

        meta = self._match_get(match, "metadata", {}) or {}
        cid = str(self._match_get(match, "id", ""))
        text = str(meta.get("text", ""))
        return Chunk(
            id=cid,
            doc_id=str(meta.get("doc_id", "")),
            text=text,
            index=int(meta.get("index", 0)),
            metadata={
                k: v for k, v in meta.items() if k not in {"text", "doc_id", "index"}
            },
        )

    def __len__(self) -> int:
        stats = self._index.describe_index_stats()
        namespaces = (
            stats.get("namespaces", {})
            if isinstance(stats, dict)
            else getattr(stats, "namespaces", {}) or {}
        )
        ns = namespaces.get(self._namespace)
        if ns is None:
            return 0
        count = ns.get("vector_count") if isinstance(ns, dict) else getattr(ns, "vector_count", 0)
        return int(count or 0)
