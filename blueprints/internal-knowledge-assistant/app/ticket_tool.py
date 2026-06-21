"""Optional light tool use — "file a ticket" over a guarded MCP boundary (Ch 19).

When the assistant can't answer (the knowledge genuinely isn't there, or the ask is an action,
not a question), the senior move is to *help anyway*: offer to file a ticket / open a request.
That is a **write action**, so it belongs behind a clean, least-privilege boundary — not stapled
into the prompt. This module composes the **mcp-server** pattern blueprint to provide exactly
that: a tiny in-process MCP server exposing one ``file_ticket`` tool, consumed through the safe
client's four guards (allow-list, schema validation, timeout, deny-by-default).

It does **not** fork mcp-server — it builds a ``Tool`` with mcp-server's own ``Tool`` type and
serves it with mcp-server's ``MCPServer`` over its ``InProcessTransport``. In production you swap
the in-process transport for stdio/HTTP and the handler for a real ticketing API (Jira, ServiceNow,
your internal queue); the guarded boundary is unchanged.

Runs free and offline: the "ticketing system" is an in-memory list, so the demo can file a ticket
with no network and no spend.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable, Mapping

# Compose mcp-server (sibling blueprint), without forking it.
_BLUEPRINTS = Path(__file__).resolve().parents[2]
_MCP_SRC = _BLUEPRINTS / "mcp-server" / "src"
if _MCP_SRC.is_dir() and str(_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(_MCP_SRC))

from mcp_server import (  # noqa: E402
    InProcessTransport,
    MCPServer,
    SafeMCPClient,
)
from mcp_server import Tool as MCPTool  # noqa: E402  (mcp-server's Tool, not agent-loop's)

# A deterministic in-memory "ticketing system". A real handler would POST to Jira/ServiceNow.
_FILED_TICKETS: list[dict[str, Any]] = []


def _file_ticket_handler(args: Mapping[str, Any]) -> dict[str, Any]:
    """Record a ticket and return its id + status (the shape a real API would return)."""
    ticket_id = f"KB-{len(_FILED_TICKETS) + 1:04d}"
    record = {
        "id": ticket_id,
        "title": args["title"],
        "body": args.get("body", ""),
        "requested_by": args.get("requested_by", "unknown"),
        "status": "open",
    }
    _FILED_TICKETS.append(record)
    return {"ticket_id": ticket_id, "status": "open"}


FILE_TICKET_TOOL = MCPTool(
    name="file_ticket",
    description="File a support/request ticket when the answer isn't in the knowledge base.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 3, "maxLength": 140},
            "body": {"type": "string", "maxLength": 2000},
            "requested_by": {"type": "string", "maxLength": 140},
        },
        "required": ["title"],
        "additionalProperties": False,
    },
    handler=_file_ticket_handler,
)


def build_ticket_client() -> SafeMCPClient:
    """Stand up the in-process MCP server for the ticket tool and a guarded client for it.

    The client is initialized, has discovered the server's tools, and has ``file_ticket`` on its
    allow-list (a deliberate, named grant — deny is the default). Anything the server might add
    later is *seen* by discovery but not callable until explicitly allowed.
    """
    server = MCPServer(name="kb-ticketing")
    server.add_tool(FILE_TICKET_TOOL)

    client = SafeMCPClient(InProcessTransport(server), allow=["file_ticket"])
    client.initialize()
    client.discover()
    return client


def file_ticket_callable(client: SafeMCPClient) -> Callable[..., Any]:
    """Expose the guarded ``file_ticket`` as a plain callable for the agent-loop's toolset.

    ``agent-loop`` consumes tools as named callables; mcp-server's ``as_agent_tool`` already wraps
    a guarded call into exactly that shape. This is the composition seam between the two pattern
    blueprints — the agent reaches the ticketing system only through the MCP guards.
    """
    return client.as_agent_tool("file_ticket")


def filed_tickets() -> list[dict[str, Any]]:
    """The tickets filed so far (demo/test introspection)."""
    return list(_FILED_TICKETS)


def reset_tickets() -> None:
    """Clear the in-memory ticket store (so the demo is reproducible across runs)."""
    _FILED_TICKETS.clear()
