"""mcp_server — a small Model Context Protocol server and a *safe* MCP client.

Two ends of MCP, both runnable with no network and no API keys:

* **Expose** — :class:`~mcp_server.server.MCPServer` registers typed *tools* and read-only
  *resources* and answers the JSON-RPC-ish methods an MCP client speaks (``initialize``,
  ``tools/list``, ``tools/call``, ``resources/list``, ``resources/read``).
* **Consume** — :class:`~mcp_server.consume.SafeMCPClient` discovers a server's tools and
  invokes them *behind guardrails*: an allow-list, argument validation against the tool's
  declared schema, a per-call timeout, and least-privilege defaults (deny unless allowed).

The transport is an in-process :class:`~mcp_server.server.InProcessTransport` so the whole
round-trip runs in one process. A real deployment swaps in stdio or HTTP+SSE behind the same
``send(request) -> response`` seam; nothing above the transport changes.

See ``README.md`` for the one-diagram model and the trade-offs.
"""

from __future__ import annotations

from .consume import (
    SafeMCPClient,
    SafetyError,
    ToolNotAllowedError,
    ValidationError,
    as_agent_tools,
)
from .resources import Resource, build_default_resources
from .server import (
    InProcessTransport,
    MCPServer,
    Transport,
    build_default_server,
)
from .tools import Tool, ToolError, build_default_tools

__all__ = [
    # server / expose side
    "MCPServer",
    "Transport",
    "InProcessTransport",
    "build_default_server",
    # tools + resources
    "Tool",
    "ToolError",
    "build_default_tools",
    "Resource",
    "build_default_resources",
    # consume side
    "SafeMCPClient",
    "SafetyError",
    "ToolNotAllowedError",
    "ValidationError",
    "as_agent_tools",
]

__version__ = "0.1.0"
