"""API boundary models — the public request/response contract (Ch 25).

These Pydantic models are the *edge* shape: they validate input at the boundary (malformed
requests are rejected before reaching a service) and serialize domain entities out. They are
deliberately separate from both the domain dataclasses and the ORM rows — three shapes, three
jobs — so an internal refactor never silently changes the wire contract. The ``from_domain``
classmethods are the only place the mapping lives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.models import (
    AgentRun,
    ChatMessage,
    Conversation,
    Document,
)

# --- runs -------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Input to start an agent run."""

    input: str = Field(
        ...,
        min_length=1,
        description="The user's prompt / task for the agent.",
        examples=["Summarize the latest quarterly report."],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-supplied metadata, echoed back for tracing.",
    )


class RunResponse(BaseModel):
    """The stored form of an agent run."""

    id: str
    status: str
    input: str
    output: str | None = None
    error: str | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, run: AgentRun) -> "RunResponse":
        return cls(
            id=run.id,
            status=run.status.value,
            input=run.input,
            output=run.output,
            error=run.error,
            created_at=run.created_at,
            metadata=run.metadata,
        )


class RunEvent(BaseModel):
    """A single Server-Sent Event emitted while a run streams.

    ``token`` carries an incremental chunk of output (present when ``type == "token"``); ``type``
    lets clients distinguish deltas from lifecycle/terminal events.
    """

    type: Literal["start", "token", "end", "error"] = "token"
    token: str | None = Field(default=None, description="Incremental output chunk.")
    data: dict[str, Any] = Field(default_factory=dict)


# --- chats ------------------------------------------------------------------------


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", max_length=255)


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            id=conversation.id, title=conversation.title, created_at=conversation.created_at
        )


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    role: Literal["user", "assistant", "system", "tool"] = "user"


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    @classmethod
    def from_domain(cls, message: ChatMessage) -> "MessageResponse":
        return cls(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
        )


# --- documents --------------------------------------------------------------------


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    source_uri: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    id: str
    title: str
    source_uri: str
    status: str
    chunk_count: int
    created_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            title=document.title,
            source_uri=document.source_uri,
            status=document.status.value,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
        )
