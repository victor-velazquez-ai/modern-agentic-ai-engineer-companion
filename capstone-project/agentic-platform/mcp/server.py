"""The capstone MCP server — enterprise tools, a resource, and a prompt.

This is the platform's tool infrastructure exposed over the **Model Context
Protocol**. Built with `FastMCP`, so the tools' type hints and docstrings
*become* the JSON schemas clients discover — write the function, get the schema.
It publishes:

* **tools** (verbs the model calls): ``search_docs`` (backed by :mod:`rag`),
  ``get_ticket`` and ``create_ticket`` (backed by the ticket tracker),
* a **resource** (read-only context the app attaches): ``runbook://{name}``,
* a **prompt** (a reusable message template the user invokes): ``triage``.

**Tool scopes are an enforcement point for ``security/``.** Each tool declares a
required scope (:data:`TOOL_SCOPES`); the platform's policy layer maps a caller's
granted scopes to the tools it may invoke. Declaring them here keeps the
permission surface in one reviewable place.

**Runs with no key and no network.** ``FastMCP`` is an optional dependency: if it
is not installed (or ``COMPANION_MOCK`` is set), :func:`build_server` returns a
:class:`~mcp.mock_server.MockMCPServer` that answers the same protocol methods
in-process. That is the path the tests and the demo use, and it keeps the module
importable anywhere Python runs.

Transport: ``FastMCP`` speaks stdio by default (``mcp.run()``) and Streamable
HTTP for a networked deployment — the same server object, a different transport.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .backends import RUNBOOKS, Backends, TicketNotFound

SERVER_NAME = "capstone-enterprise"

# Tool name -> the permission scope a caller must hold to invoke it. The MCP
# server *declares* these; security/ (the policy layer) *enforces* them. Keeping
# the map next to the tools means the scopes can't drift from the tool set.
TOOL_SCOPES: dict[str, str] = {
    "search_docs": "docs:read",
    "get_ticket": "tickets:read",
    "create_ticket": "tickets:write",
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def fastmcp_available() -> bool:
    """True if the real ``FastMCP`` package can be imported."""
    try:
        import mcp.server.fastmcp  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def build_server(backends: Backends | None = None) -> Any:
    """Build and return the MCP server with all tools/resources/prompts registered.

    Returns a real ``FastMCP`` instance when the package is installed and
    ``COMPANION_MOCK`` is not set; otherwise a :class:`MockMCPServer` exposing the
    identical tool/resource/prompt surface in-process. Either way, the
    registration logic below is the single source of truth for *what* the server
    exposes — only the framework object differs.
    """
    backends = backends or Backends()

    if _truthy(os.getenv("COMPANION_MOCK", "1")) or not fastmcp_available():
        from .mock_server import MockMCPServer

        return _register(MockMCPServer(SERVER_NAME), backends)

    from mcp.server.fastmcp import FastMCP  # type: ignore

    return _register(FastMCP(SERVER_NAME), backends)


def _register(mcp: Any, backends: Backends) -> Any:
    """Register the three tools, the runbook resource, and the triage prompt.

    ``mcp`` is duck-typed: both ``FastMCP`` and ``MockMCPServer`` expose
    ``.tool()``, ``.resource()`` and ``.prompt()`` decorators with the same
    contract, so this body is framework-agnostic.
    """

    @mcp.tool()
    def search_docs(query: str, top_k: int = 5) -> str:
        """Search the internal knowledge base for documents relevant to a query.

        Use this to ground answers in company documentation before responding.
        Returns a JSON array of ``{doc_id, title, snippet, score}`` ordered by
        relevance (highest first).

        Args:
            query: Natural-language search query (what the user is asking about).
            top_k: Maximum number of documents to return (1-10).
        """
        top_k = max(1, min(int(top_k), 10))
        results = backends.docs.search(query, top_k=top_k)
        return json.dumps([d.to_dict() for d in results])

    @mcp.tool()
    def get_ticket(ticket_id: str) -> str:
        """Look up a single support/engineering ticket by its id.

        Returns the ticket as a JSON object, or a JSON object with an ``error``
        field if no ticket matches the id. Use this to fetch ticket context
        before answering a question about it.

        Args:
            ticket_id: The ticket identifier, e.g. ``TICK-1001``.
        """
        try:
            return json.dumps(backends.tickets.get(ticket_id).to_dict())
        except TicketNotFound:
            return json.dumps({"error": f"ticket {ticket_id!r} not found"})

    @mcp.tool()
    def create_ticket(title: str, description: str, priority: str = "medium") -> str:
        """Create a new ticket in the tracker and return it as JSON.

        This is a **write** tool (scope ``tickets:write``) — only callers granted
        that scope may invoke it, and a human-approval gate may sit in front of it
        for risky automations. Returns the created ticket including its assigned
        ``ticket_id``.

        Args:
            title: Short, descriptive ticket title.
            description: Full description of the issue or request.
            priority: One of ``low``, ``medium``, ``high`` (defaults to medium).
        """
        priority = priority if priority in {"low", "medium", "high"} else "medium"
        ticket = backends.tickets.create(
            title=title, description=description, priority=priority
        )
        return json.dumps(ticket.to_dict())

    @mcp.resource("runbook://{name}")
    def runbook(name: str) -> str:
        """Return the named operational runbook as Markdown (read-only context).

        A *resource* is a noun the app attaches to context, not a verb the model
        invokes — reading it can never mutate state. Available runbooks:
        ``incident``, ``onboarding``.
        """
        return RUNBOOKS.get(name, f"# Unknown runbook: {name}\n")

    @mcp.prompt()
    def triage(ticket_id: str) -> str:
        """A reusable prompt that asks the model to triage a ticket.

        Prompts are templates the *user* invokes (vs. tools the model calls).
        This one instructs the assistant to pull the ticket, search the docs, and
        propose next steps — the platform's standard triage workflow.
        """
        return (
            f"Triage ticket {ticket_id}.\n"
            "1. Call get_ticket to load its details.\n"
            "2. Call search_docs for relevant runbooks or KB articles.\n"
            "3. Summarize the issue, cite the docs you used, and recommend the "
            "next action. If the issue is novel, draft a create_ticket for "
            "follow-up rather than guessing.\n"
        )

    return mcp


def main() -> None:
    """Entry point: run the server over its default transport (stdio for FastMCP).

    In ``COMPANION_MOCK`` mode there is no transport to serve — the mock is
    exercised in-process by the demo and tests — so this prints how to run for
    real instead of blocking on a socket.
    """
    server = build_server()
    run = getattr(server, "run", None)
    if callable(run) and fastmcp_available() and not _truthy(os.getenv("COMPANION_MOCK", "1")):
        run()  # pragma: no cover - requires the real FastMCP + a host
    else:
        print(
            f"[{SERVER_NAME}] built in MOCK mode "
            f"(tools: {', '.join(sorted(TOOL_SCOPES))}). "
            "Install 'mcp' and unset COMPANION_MOCK to serve over stdio/HTTP."
        )


if __name__ == "__main__":
    main()
