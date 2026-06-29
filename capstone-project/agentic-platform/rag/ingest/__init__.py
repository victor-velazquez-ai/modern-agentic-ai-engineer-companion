"""``rag.ingest`` — the first half of the pipeline: get text in, get vectors out.

Three stages, one per module, in the order data flows through them:

* :mod:`rag.ingest.loaders` — raw sources (strings, files, a directory tree) →
  :class:`Document` objects with provenance metadata.
* :mod:`rag.ingest.chunk` — :class:`Document` → overlapping, self-contained :class:`Chunk` s.
  Chunking is the decision that bounds everything downstream: a retriever can only return what
  ingestion preserved.
* :mod:`rag.ingest.embed` — :class:`Chunk` → :class:`EmbeddedChunk` (a unit-norm vector).
  Mock-by-default (deterministic feature hashing); real embeddings via the platform ``llm/``
  gateway when ``COMPANION_MOCK=0``.

The shared :mod:`rag.ingest.tokenize` keeps dense, keyword, and rerank channels seeing the same
tokens, so they never disagree about what a document contains.
"""

from __future__ import annotations

from .chunk import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    Chunk,
    chunk_documents,
    chunk_text,
)
from .embed import (
    DEFAULT_EMBEDDING_DIM,
    EmbeddedChunk,
    Embedder,
    MockEmbedder,
    embed_chunks,
    embed_query,
    get_embedder,
)
from .loaders import Document, load_directory, load_documents, load_text, new_document_id

__all__ = [
    # loaders
    "Document",
    "load_text",
    "load_documents",
    "load_directory",
    "new_document_id",
    # chunk
    "Chunk",
    "chunk_text",
    "chunk_documents",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    # embed
    "Embedder",
    "MockEmbedder",
    "EmbeddedChunk",
    "DEFAULT_EMBEDDING_DIM",
    "embed_chunks",
    "embed_query",
    "get_embedder",
]
