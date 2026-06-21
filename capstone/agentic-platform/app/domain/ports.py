"""Domain ports — the abstract seams the core depends on (Ch 28).

A *port* is an interface the domain declares and an outer layer implements. Expressing them as
``typing.Protocol`` means the domain depends on a *shape*, not on a concrete class in ``db/`` or
on a model SDK — the hexagonal-architecture seam. ``services/`` and ``db/`` provide the
adapters; tests provide fakes. Because these are structural protocols, an adapter satisfies a
port just by having the right methods (no inheritance, no import of this module required).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol, runtime_checkable

from app.domain.models import (
    AgentRun,
    ChatMessage,
    Conversation,
    Document,
)


@runtime_checkable
class RunRepository(Protocol):
    """Persistence port for :class:`~app.domain.models.AgentRun`.

    Every method is tenant-scoped: an implementation must never return a run belonging to a
    different ``tenant_id``. That scoping is the multi-tenancy boundary (Ch 26).
    """

    async def add(self, run: AgentRun) -> AgentRun: ...

    async def get(self, tenant_id: str, run_id: str) -> AgentRun | None: ...

    async def update(self, run: AgentRun) -> AgentRun: ...

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[AgentRun]: ...


@runtime_checkable
class ChatRepository(Protocol):
    """Persistence port for conversations and their messages."""

    async def create_conversation(self, conversation: Conversation) -> Conversation: ...

    async def get_conversation(
        self, tenant_id: str, conversation_id: str
    ) -> Conversation | None: ...

    async def add_message(self, message: ChatMessage) -> ChatMessage: ...

    async def list_messages(
        self, tenant_id: str, conversation_id: str
    ) -> Sequence[ChatMessage]: ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Persistence port for the RAG document catalog."""

    async def add(self, document: Document) -> Document: ...

    async def get(self, tenant_id: str, document_id: str) -> Document | None: ...

    async def list_for_tenant(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Document]: ...


class AgentEvent(Protocol):
    """Structural shape of a streamed agent event (one SSE frame's payload).

    The concrete event type lives in ``services`` (so the domain need not depend on Pydantic),
    but the domain pins the shape the engine must produce.
    """

    type: str
    token: str | None


@runtime_checkable
class AgentEngine(Protocol):
    """The single seam between the platform and *a* reasoning engine (Ch 12, 18).

    The backend never imports a model SDK or a framework directly — it depends on this port. The
    concrete adapter wraps the capstone ``agents/raw`` loop (or a framework variant, or, in MOCK
    mode, a canned engine). ``run`` returns the final text; ``stream`` yields events as the loop
    progresses.
    """

    async def run(self, task: str, *, tenant_id: str) -> str: ...

    def stream(self, task: str, *, tenant_id: str) -> AsyncIterator[AgentEvent]: ...
