"""Local Chroma adapter — the "real persistence" swap (Ch 13).

Same :class:`~rag_pipeline.stores.base.VectorStore` surface as the in-memory store, backed by a
local `Chroma <https://www.trychroma.com/>`_ collection so vectors survive process restarts and
scale past what fitting everything in a Python list comfortably allows.

**Import-safety.** ``chromadb`` is an optional, heavyweight dependency (it is in
``requirements.txt`` but not needed for the default MOCK path). So this module imports it
*lazily, inside ``__init__``* and raises a friendly :class:`RuntimeError` if it is missing. That
keeps ``import rag_pipeline`` working with zero third-party deps installed — the whole point of
runnable-by-default — while still giving you real persistence when you opt in.

**Cloud swap (Pinecone).** Going from local to cloud is *another adapter*, not a rewrite: a
``PineconeVectorStore`` would implement the same three methods (``add`` -> ``upsert``,
``search`` -> ``query``, ``keyword_search`` -> a metadata/sparse query or a sidecar BM25 index)
and construction would change from ``ChromaVectorStore(...)`` to ``PineconeVectorStore(...)``.
The retriever, reranker, and demo do not change. See the README "Store-adapter swap" section.
"""

from __future__ import annotations

from typing import Sequence

from ..embed import EmbeddedChunk
from .base import StoredChunk
from .memory import _tokens  # reuse the lexical scorer for the keyword channel

_INSTALL_HINT = (
    "ChromaVectorStore requires the optional 'chromadb' package. Install it with "
    "`pip install chromadb` (it is listed in requirements.txt). The default in-memory store "
    "needs no extra dependencies — use InMemoryVectorStore for MOCK/offline runs."
)


class ChromaVectorStore:
    """A :class:`~rag_pipeline.stores.base.VectorStore` backed by a local Chroma collection.

    Args:
        collection_name: Chroma collection to create/use.
        persist_directory: Where Chroma persists data. ``None`` uses an ephemeral in-process
            client (handy for tests of the adapter itself).
    """

    def __init__(
        self,
        collection_name: str = "rag_pipeline",
        *,
        persist_directory: str | None = None,
    ) -> None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised only without chromadb.
            raise RuntimeError(_INSTALL_HINT) from exc

        if persist_directory is None:
            client = chromadb.EphemeralClient()
        else:
            client = chromadb.PersistentClient(path=persist_directory)
        # Cosine space to match the in-memory store's similarity, so retrieval ranks agree.
        self._collection = client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add(self, embedded: Sequence[EmbeddedChunk]) -> None:
        if not embedded:
            return
        self._collection.upsert(
            ids=[e.chunk.id for e in embedded],
            embeddings=[list(e.vector) for e in embedded],
            documents=[e.chunk.text for e in embedded],
            metadatas=[
                {"doc_id": e.chunk.doc_id, "index": e.chunk.index, **e.chunk.metadata}
                for e in embedded
            ],
        )

    def search(
        self, query_vector: Sequence[float], k: int
    ) -> list[StoredChunk]:
        if k <= 0 or len(self) == 0:
            return []
        result = self._collection.query(
            query_embeddings=[list(query_vector)],
            n_results=min(k, len(self)),
            include=["documents", "metadatas", "distances"],
        )
        return self._to_hits(result)

    def keyword_search(self, query: str, k: int) -> list[StoredChunk]:
        # Chroma has no first-class BM25; for the keyword channel we pull documents and apply the
        # same lexical scorer as the in-memory store. A production swap would back this with a
        # real full-text/sparse index. Behavior stays identical to the default store.
        if k <= 0 or len(self) == 0:
            return []
        q_tokens = _tokens(query)
        if not q_tokens:
            return []
        dump = self._collection.get(include=["documents", "metadatas"])
        import math

        from ..ingest import Chunk

        scored: list[StoredChunk] = []
        for cid, text, meta in zip(
            dump["ids"], dump["documents"], dump["metadatas"]
        ):
            c_tokens = _tokens(text or "")
            overlap = len(q_tokens & c_tokens)
            if overlap == 0 or not c_tokens:
                continue
            meta = meta or {}
            chunk = Chunk(
                id=cid,
                doc_id=str(meta.get("doc_id", "")),
                text=text or "",
                index=int(meta.get("index", 0)),
                metadata={
                    kk: vv for kk, vv in meta.items() if kk not in {"doc_id", "index"}
                },
            )
            scored.append(
                StoredChunk(chunk=chunk, score=overlap / math.sqrt(len(c_tokens)))
            )
        scored.sort(key=lambda s: (-s.score, s.chunk.id))
        return scored[:k]

    def _to_hits(self, result: dict) -> list[StoredChunk]:
        from ..ingest import Chunk

        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        distances = result["distances"][0]
        hits: list[StoredChunk] = []
        for cid, text, meta, dist in zip(ids, docs, metas, distances):
            meta = meta or {}
            chunk = Chunk(
                id=cid,
                doc_id=str(meta.get("doc_id", "")),
                text=text or "",
                index=int(meta.get("index", 0)),
                metadata={
                    kk: vv for kk, vv in meta.items() if kk not in {"doc_id", "index"}
                },
            )
            # Chroma returns cosine *distance* in [0, 2]; convert to similarity.
            hits.append(StoredChunk(chunk=chunk, score=1.0 - float(dist)))
        return hits

    def __len__(self) -> int:
        return int(self._collection.count())
