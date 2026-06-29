"""Document routes: register sources and browse the RAG catalog (Ch 13, 25).

- ``POST /v1/documents``        — register a source document (ingestion enqueued).
- ``GET  /v1/documents``        — list the tenant's corpus.
- ``GET  /v1/documents/{id}``   — fetch one document's catalog entry + status.

Transport only — delegates to ``DocumentService``. The chunk/embed/index work happens in a
worker (Ch 31); these routes expose the catalog the agents retrieve over.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.schemas import DocumentCreate, DocumentResponse
from app.core.auth import Principal, get_current_principal
from app.core.deps import get_document_service
from app.core.ratelimit import enforce_rate_limit
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=202,
    summary="Register a document (ingestion enqueued)",
    dependencies=[Depends(enforce_rate_limit)],
)
async def register_document(
    body: DocumentCreate,
    documents: DocumentService = Depends(get_document_service),
    principal: Principal = Depends(get_current_principal),
) -> DocumentResponse:
    document = await documents.register_document(
        tenant_id=principal.tenant_id,
        title=body.title,
        source_uri=body.source_uri,
        metadata=body.metadata,
    )
    return DocumentResponse.from_domain(document)


@router.get("", response_model=list[DocumentResponse], summary="List the tenant's documents")
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    documents: DocumentService = Depends(get_document_service),
    principal: Principal = Depends(get_current_principal),
) -> list[DocumentResponse]:
    items = await documents.list_documents(
        tenant_id=principal.tenant_id, limit=limit, offset=offset
    )
    return [DocumentResponse.from_domain(d) for d in items]


@router.get("/{document_id}", response_model=DocumentResponse, summary="Fetch one document")
async def get_document(
    document_id: str,
    documents: DocumentService = Depends(get_document_service),
    principal: Principal = Depends(get_current_principal),
) -> DocumentResponse:
    document = await documents.get_document(
        tenant_id=principal.tenant_id, document_id=document_id
    )
    return DocumentResponse.from_domain(document)
