"""Domain entities + value objects — plain Python, no framework (Ch 28).

These are the platform's nouns and their rules, expressed as dataclasses and enums. No ORM, no
Pydantic, no FastAPI: a domain object is constructible and testable with nothing but the
standard library. The ORM rows in ``app.db.models`` map *to* these; the API schemas in
``app.api.schemas`` map *from* them. The domain is the only place that owns the ``AgentRun``
state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from app.domain.errors import InvalidStateTransitionError


def utcnow() -> datetime:
    """Timezone-aware UTC now — the only clock the domain uses."""
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """A sortable-enough, prefixed id (``run_ab12...``)."""
    return f"{prefix}_{uuid4().hex}"


class RunStatus(str, Enum):
    """Lifecycle of an agent run. The transitions are enforced by ``AgentRun.transition_to``."""

    QUEUED = "queued"            # accepted, awaiting a worker
    RUNNING = "running"          # a worker is executing the loop
    AWAITING_APPROVAL = "awaiting_approval"  # paused on a risky tool (Ch 20)
    COMPLETED = "completed"      # finished with a final answer
    FAILED = "failed"            # errored out / recovery exhausted
    CANCELLED = "cancelled"      # stopped by a caller


# Allowed forward transitions. Terminal states have no outgoing edges.
_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.AWAITING_APPROVAL,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.AWAITING_APPROVAL: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

_TERMINAL_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
)


@dataclass
class AgentRun:
    """One execution of an agent against a task, owned by a tenant.

    The run is created ``QUEUED`` (the API enqueues; a worker does the long work — Ch 31). It is
    the single entity the streaming endpoint, the worker, and the approval gate all coordinate
    around.
    """

    tenant_id: str
    input: str
    id: str = field(default_factory=lambda: new_id("run"))
    status: RunStatus = RunStatus.QUEUED
    output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def is_terminal(self) -> bool:
        """True once the run can no longer change state."""
        return self.status in _TERMINAL_STATES

    def transition_to(self, target: RunStatus) -> None:
        """Move the run to ``target`` if the transition is legal, else raise.

        Centralizing the state machine here (not in a route or a worker) is what keeps every
        caller honest: there is exactly one definition of which moves are allowed.
        """
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStateTransitionError("AgentRun", self.status.value, target.value)
        self.status = target
        self.updated_at = utcnow()

    def complete(self, output: str) -> None:
        """Mark the run finished with its final answer."""
        self.transition_to(RunStatus.COMPLETED)
        self.output = output

    def fail(self, error: str) -> None:
        """Mark the run failed with a reason."""
        self.transition_to(RunStatus.FAILED)
        self.error = error


class MessageRole(str, Enum):
    """The author of a chat message."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """One turn in a conversation. Conversations are ordered lists of these."""

    conversation_id: str
    role: MessageRole
    content: str
    id: str = field(default_factory=lambda: new_id("msg"))
    created_at: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """A chat thread owned by a tenant, grouping ordered ``ChatMessage`` turns."""

    tenant_id: str
    title: str = "New conversation"
    id: str = field(default_factory=lambda: new_id("conv"))
    created_at: datetime = field(default_factory=utcnow)


class DocumentStatus(str, Enum):
    """Ingestion lifecycle of a document in the RAG corpus (Ch 13)."""

    PENDING = "pending"        # registered, not yet chunked/embedded
    INDEXED = "indexed"        # chunked, embedded, queryable
    FAILED = "failed"          # ingestion errored


@dataclass
class Document:
    """A source document in the tenant's private corpus, retrievable by the agents.

    The chunk/embed/index work lives in ``rag/`` (Ch 13); this entity is the catalog row the API
    exposes and the worker updates as ingestion progresses.
    """

    tenant_id: str
    title: str
    source_uri: str
    id: str = field(default_factory=lambda: new_id("doc"))
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)
