"""SQLAlchemy repositories — the adapters that satisfy the domain ports (Ch 28, 30).

Each repository implements one of the ``app.domain.ports`` protocols on top of an
``AsyncSession``, translating ORM rows ↔ domain entities at the boundary. The domain never sees
a ``...Row``; the rest of the app never sees a raw SQL row. Every query is filtered by
``tenant_id`` so a repository physically cannot return another tenant's data.

These classes have no decorator declaring they implement the ports — they satisfy them
structurally (``Protocol``), which is exactly the loose coupling the hexagonal seam buys.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRunRow,
    ChatMessageRow,
    ConversationRow,
    DocumentRow,
)
from app.domain.models import (
    AgentRun,
    ChatMessage,
    Conversation,
    Document,
    DocumentStatus,
    MessageRole,
    RunStatus,
)

# --- mappers (ORM row <-> domain entity) ------------------------------------------


def _run_to_domain(row: AgentRunRow) -> AgentRun:
    run = AgentRun(
        tenant_id=row.tenant_id,
        input=row.input,
        id=row.id,
        status=RunStatus(row.status),
        output=row.output,
        error=row.error,
        metadata=dict(row.run_metadata or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    return run


def _run_apply(row: AgentRunRow, run: AgentRun) -> None:
    row.status = run.status.value
    row.input = run.input
    row.output = run.output
    row.error = run.error
    row.run_metadata = dict(run.metadata)


def _document_to_domain(row: DocumentRow) -> Document:
    return Document(
        tenant_id=row.tenant_id,
        title=row.title,
        source_uri=row.source_uri,
        id=row.id,
        status=DocumentStatus(row.status),
        chunk_count=row.chunk_count,
        metadata=dict(row.doc_metadata or {}),
        created_at=row.created_at,
    )


# --- repositories -----------------------------------------------------------------


class SqlAlchemyRunRepository:
    """``RunRepository`` adapter backed by ``AgentRunRow``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: AgentRun) -> AgentRun:
        row = AgentRunRow(id=run.id, tenant_id=run.tenant_id, status=run.status.value, input=run.input)
        _run_apply(row, run)
        self._session.add(row)
        await self._session.flush()
        return _run_to_domain(row)

    async def get(self, tenant_id: str, run_id: str) -> AgentRun | None:
        row = await self._session.get(AgentRunRow, run_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return _run_to_domain(row)

    async def update(self, run: AgentRun) -> AgentRun:
        row = await self._session.get(AgentRunRow, run.id)
        if row is None or row.tenant_id != run.tenant_id:
            # Upsert semantics keep the worker path simple if the row was evicted.
            return await self.add(run)
        _run_apply(row, run)
        await self._session.flush()
        return _run_to_domain(row)

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[AgentRun]:
        stmt = (
            select(AgentRunRow)
            .where(AgentRunRow.tenant_id == tenant_id)
            .order_by(AgentRunRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_run_to_domain(r) for r in rows]


class SqlAlchemyChatRepository:
    """``ChatRepository`` adapter backed by ``ConversationRow`` + ``ChatMessageRow``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self, conversation: Conversation) -> Conversation:
        row = ConversationRow(
            id=conversation.id,
            tenant_id=conversation.tenant_id,
            title=conversation.title,
        )
        self._session.add(row)
        await self._session.flush()
        return conversation

    async def get_conversation(
        self, tenant_id: str, conversation_id: str
    ) -> Conversation | None:
        row = await self._session.get(ConversationRow, conversation_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return Conversation(
            tenant_id=row.tenant_id, title=row.title, id=row.id, created_at=row.created_at
        )

    async def add_message(self, message: ChatMessage) -> ChatMessage:
        row = ChatMessageRow(
            id=message.id,
            tenant_id=message.metadata.get("tenant_id", ""),
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            message_metadata=dict(message.metadata),
        )
        self._session.add(row)
        await self._session.flush()
        return message

    async def list_messages(
        self, tenant_id: str, conversation_id: str
    ) -> Sequence[ChatMessage]:
        stmt = (
            select(ChatMessageRow)
            .where(
                ChatMessageRow.conversation_id == conversation_id,
                ChatMessageRow.tenant_id == tenant_id,
            )
            .order_by(ChatMessageRow.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            ChatMessage(
                conversation_id=r.conversation_id,
                role=MessageRole(r.role),
                content=r.content,
                id=r.id,
                created_at=r.created_at,
                metadata=dict(r.message_metadata or {}),
            )
            for r in rows
        ]


class SqlAlchemyDocumentRepository:
    """``DocumentRepository`` adapter backed by ``DocumentRow``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> Document:
        row = DocumentRow(
            id=document.id,
            tenant_id=document.tenant_id,
            title=document.title,
            source_uri=document.source_uri,
            status=document.status.value,
            chunk_count=document.chunk_count,
            doc_metadata=dict(document.metadata),
        )
        self._session.add(row)
        await self._session.flush()
        return document

    async def get(self, tenant_id: str, document_id: str) -> Document | None:
        row = await self._session.get(DocumentRow, document_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return _document_to_domain(row)

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Document]:
        stmt = (
            select(DocumentRow)
            .where(DocumentRow.tenant_id == tenant_id)
            .order_by(DocumentRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_document_to_domain(r) for r in rows]
