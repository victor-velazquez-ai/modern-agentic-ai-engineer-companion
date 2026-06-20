"""Vector-store adapters.

``base`` defines the :class:`~rag_pipeline.stores.base.VectorStore` Protocol — the seam that
keeps the rest of the pipeline ignorant of *where* vectors live. ``memory`` is the
deterministic in-memory default (MOCK); ``chroma`` is the local-persistence adapter, with the
cloud Pinecone swap documented as the next adapter to add.
"""

from .base import StoredChunk, VectorStore
from .chroma import ChromaVectorStore
from .memory import InMemoryVectorStore

__all__ = ["VectorStore", "StoredChunk", "InMemoryVectorStore", "ChromaVectorStore"]
