"""mcp — the platform's tool infrastructure over the Model Context Protocol.

Two ends, both runnable offline with no API keys:

* **Expose** — :func:`mcp.server.build_server` builds a ``FastMCP`` server (or an
  in-process :class:`~mcp.mock_server.MockMCPServer` fallback) that publishes the
  platform's enterprise tools (``search_docs``, ``get_ticket``, ``create_ticket``),
  a ``runbook://{name}`` resource, and a ``triage`` prompt. Tool *scopes*
  (:data:`mcp.server.TOOL_SCOPES`) are an enforcement point for ``security/``.
* **Consume** — :class:`mcp.consume.SafeMCPClient` discovers a server's tools and
  invokes them behind guardrails (allow-list, schema validation, timeout,
  least-privilege), exporting the allowed set as the agent loop's toolset.

The package name shadows the third-party ``mcp`` SDK only *within this project's*
import path; :mod:`mcp.server` imports the real SDK lazily as
``mcp.server.fastmcp`` so there is no conflict at module load.
"""

from __future__ import annotations

from .backends import (
    Backends,
    Document,
    MockDocSearch,
    MockTicketTracker,
    Ticket,
    TicketNotFound,
)
from .consume import (
    SafeMCPClient,
    SafetyError,
    ToolNotAllowedError,
    ValidationError,
    as_agent_tools,
)
from .mock_server import InProcessTransport, MockMCPServer
from .server import SERVER_NAME, TOOL_SCOPES, build_server

__all__ = [
    # expose side
    "build_server",
    "SERVER_NAME",
    "TOOL_SCOPES",
    "MockMCPServer",
    "InProcessTransport",
    # backends
    "Backends",
    "Document",
    "Ticket",
    "TicketNotFound",
    "MockDocSearch",
    "MockTicketTracker",
    # consume side
    "SafeMCPClient",
    "SafetyError",
    "ToolNotAllowedError",
    "ValidationError",
    "as_agent_tools",
]

__version__ = "0.1.0"
