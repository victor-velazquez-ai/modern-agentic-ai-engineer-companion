"""ORM row models (Ch 30).

These are the *storage* shape — deliberately separate from the domain entities in
``app.domain.models``. The repositories translate between the two. Keeping them apart means a
schema change (a column rename, a denormalization) does not ripple into business logic, and the
domain stays free of any ORM import.

JSON metadata is stored in a portable ``JSON`` column so the same models run on both Postgres
(``jsonb``) and the SQLite used in tests. Vector embeddings live in ``rag/`` (pgvector); this
catalog only tracks ingestion status and chunk counts.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantMixin, TimestampMixin


class AgentRunRow(Base, TenantMixin, TimestampMixin):
    """Persistent form of :class:`~app.domain.models.AgentRun`."""

    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class ConversationRow(Base, TenantMixin, TimestampMixin):
    """Persistent form of :class:`~app.domain.models.Conversation`."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    messages: Mapped[list["ChatMessageRow"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessageRow.created_at",
    )


class ChatMessageRow(Base, TenantMixin, TimestampMixin):
    """Persistent form of :class:`~app.domain.models.ChatMessage`."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    conversation: Mapped["ConversationRow"] = relationship(back_populates="messages")


class DocumentRow(Base, TenantMixin, TimestampMixin):
    """Persistent form of :class:`~app.domain.models.Document` (the RAG catalog)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
