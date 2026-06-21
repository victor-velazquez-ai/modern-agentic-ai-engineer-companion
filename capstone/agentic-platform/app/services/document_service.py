"""Document use-cases: register sources and kick off ingestion (Ch 13, 25).

This service owns the *catalog* side of RAG: registering a document, listing the tenant's
corpus, and handing ingestion off to a background worker. The chunk → embed → index work lives
in the ``rag/`` package and runs in a Celery task (Ch 31); here we only create the catalog row
in ``PENDING`` and enqueue the job. The worker flips the row to ``INDEXED`` (or ``FAILED``).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.errors import EntityNotFoundError
from app.domain.models import Document
from app.domain.ports import DocumentRepository


class DocumentService:
    """Use-cases over the RAG document catalog."""

    def __init__(self, *, documents: DocumentRepository) -> None:
        self._documents = documents

    async def register_document(
        self,
        *,
        tenant_id: str,
        title: str,
        source_uri: str,
        metadata: dict | None = None,
    ) -> Document:
        """Create a ``PENDING`` catalog row. Ingestion is enqueued separately (worker)."""
        document = Document(
            tenant_id=tenant_id,
            title=title,
            source_uri=source_uri,
            metadata=metadata or {},
        )
        stored = await self._documents.add(document)
        # ▢ In the assembled stack, enqueue the ingest task here:
        #     workers.tasks.ingestion.ingest_document.delay(stored.id, tenant_id)
        # Kept out of the service so the domain/use-case layer never imports Celery directly;
        # the worker-enqueue adapter is wired in app.core.deps.
        return stored

    async def get_document(self, *, tenant_id: str, document_id: str) -> Document:
        """Fetch one document for the tenant, or raise ``EntityNotFoundError``."""
        document = await self._documents.get(tenant_id, document_id)
        if document is None:
            raise EntityNotFoundError("Document", document_id)
        return document

    async def list_documents(
        self, *, tenant_id: str, limit: int = 50, offset: int = 0
    ) -> Sequence[Document]:
        """List the tenant's documents, newest first."""
        return await self._documents.list_for_tenant(tenant_id, limit=limit, offset=offset)
