"""Mock backends the MCP tools call — RAG search + a ticket tracker.

The capstone's MCP server exposes *enterprise* tools (document search, ticket
lookup/create) over the Model Context Protocol. In production those tools call
the platform's real subsystems: ``search_docs`` is backed by :mod:`rag` (the
``Retriever`` protocol), and the ticket tools hit an external tracker (Jira,
Linear, ...) through a service adapter.

Here they are backed by **deterministic, in-memory mocks** so the server is
runnable for free and offline — no vector store, no network, no API keys. The
*shape* of each function (its signature, its return type) is identical to the
production version; only the body differs. Swap the bodies for real adapters and
nothing above this module changes.

This is the seam the capstone leans on everywhere: depend on a protocol, inject
a real or mock implementation. See ``mcp/README.md`` for how this wires into the
FastMCP server.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Document:
    """One retrieved document chunk: where it came from, and how it scored."""

    doc_id: str
    title: str
    snippet: str
    score: float

    def to_dict(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "snippet": self.snippet,
            "score": round(self.score, 4),
        }


@runtime_checkable
class DocSearch(Protocol):
    """The retrieval seam the ``search_docs`` tool depends on.

    In the full platform this is satisfied by ``rag.retrieve.Retriever``. Here it
    is satisfied by :class:`MockDocSearch`. The tool never imports a concrete
    store — only this protocol.
    """

    def search(self, query: str, *, top_k: int = 5) -> list[Document]:
        """Return up to ``top_k`` documents most relevant to ``query``."""
        ...


# A tiny, fixed corpus so retrieval is deterministic and explainable in tests.
_CORPUS: tuple[tuple[str, str, str], ...] = (
    (
        "kb-001",
        "Resetting a user's MFA device",
        "To reset multi-factor auth, open Admin > Security, revoke the lost "
        "device, and email the user a fresh enrollment link. Never disable MFA.",
    ),
    (
        "kb-002",
        "Refund policy for annual plans",
        "Annual plans are refundable pro-rata within 30 days. After 30 days, "
        "offer account credit instead of a cash refund; escalate exceptions.",
    ),
    (
        "kb-003",
        "Diagnosing elevated API latency",
        "Check the p99 latency dashboard, then the gateway cache hit rate. A "
        "cold cache after deploy is the usual cause; pre-warm before rollout.",
    ),
    (
        "kb-004",
        "Onboarding a new enterprise tenant",
        "Create the tenant record, provision an isolated schema, seed default "
        "roles, then invite the admin. Tenancy is enforced in the data layer.",
    ),
)


class MockDocSearch:
    """A deterministic, offline stand-in for the RAG retriever.

    Scores documents by simple lexical overlap between the query terms and each
    document's title + snippet. Good enough to exercise the *protocol* and the
    tool wiring; the real retriever does chunk → embed → retrieve → rerank.
    """

    def __init__(self, corpus: tuple[tuple[str, str, str], ...] = _CORPUS) -> None:
        self._docs = [
            Document(doc_id=doc_id, title=title, snippet=snippet, score=0.0)
            for doc_id, title, snippet in corpus
        ]

    def search(self, query: str, *, top_k: int = 5) -> list[Document]:
        terms = {t for t in query.lower().split() if t}
        scored: list[Document] = []
        for doc in self._docs:
            haystack = f"{doc.title} {doc.snippet}".lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                # Normalise so the score lands in (0, 1]; deterministic.
                score = hits / max(len(terms), 1)
                scored.append(
                    Document(doc.doc_id, doc.title, doc.snippet, score)
                )
        scored.sort(key=lambda d: (-d.score, d.doc_id))
        return scored[: max(top_k, 0)]


@dataclass
class Ticket:
    """A support/engineering ticket in the mock tracker."""

    ticket_id: str
    title: str
    status: str
    priority: str
    description: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "description": self.description,
            "created_at": self.created_at,
        }


class TicketNotFound(KeyError):
    """Raised when a ticket id is not present in the tracker."""


@runtime_checkable
class TicketTracker(Protocol):
    """The tracker seam the ticket tools depend on (Jira/Linear in production)."""

    def get(self, ticket_id: str) -> Ticket:
        """Fetch one ticket by id, or raise :class:`TicketNotFound`."""
        ...

    def create(self, *, title: str, description: str, priority: str = "medium") -> Ticket:
        """Create a ticket and return it (with a server-assigned id)."""
        ...


class MockTicketTracker:
    """An in-memory ticket tracker seeded with one example ticket.

    Ids are deterministic for seeded data and content-derived for created
    tickets, so a given ``create`` call yields a stable id in tests without a
    real database sequence.
    """

    _SEED = Ticket(
        ticket_id="TICK-1001",
        title="Customer cannot log in after password reset",
        status="open",
        priority="high",
        description="User reports the reset link 401s. Suspected clock skew on "
        "the token; reproduce against staging before escalating.",
        created_at="2024-01-15T09:30:00+00:00",
    )

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {self._SEED.ticket_id: self._SEED}
        self._counter = itertools.count(1002)

    def get(self, ticket_id: str) -> Ticket:
        try:
            return self._tickets[ticket_id]
        except KeyError as exc:
            raise TicketNotFound(ticket_id) from exc

    def create(self, *, title: str, description: str, priority: str = "medium") -> Ticket:
        # Deterministic id: a content hash keeps tests reproducible without a DB.
        digest = hashlib.sha1(f"{title}\n{description}".encode()).hexdigest()[:6]
        ticket = Ticket(
            ticket_id=f"TICK-{digest.upper()}",
            title=title,
            status="open",
            priority=priority,
            description=description,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket


@dataclass
class Backends:
    """The set of backends the MCP tools are wired against.

    Bundling them lets the server be constructed with mocks in tests/offline and
    with real adapters in production via one injection point.
    """

    docs: DocSearch = field(default_factory=MockDocSearch)
    tickets: TicketTracker = field(default_factory=MockTicketTracker)


# A short runbook the server exposes as an MCP *resource* (read-only context).
RUNBOOKS: dict[str, str] = {
    "incident": (
        "# Incident Response Runbook\n\n"
        "1. Acknowledge the page and declare severity.\n"
        "2. Open an incident channel; assign an IC.\n"
        "3. Mitigate first, root-cause second.\n"
        "4. Post a status update every 30 minutes.\n"
        "5. After resolution, write a blameless postmortem.\n"
    ),
    "onboarding": (
        "# Tenant Onboarding Runbook\n\n"
        "1. Create the tenant record and isolated schema.\n"
        "2. Seed default roles and the admin invite.\n"
        "3. Verify tenancy isolation with the smoke suite.\n"
    ),
}
