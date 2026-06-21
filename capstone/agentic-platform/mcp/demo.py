#!/usr/bin/env python3
"""Runnable demo — the capstone MCP server ↔ a safe client, MOCK and offline.

Run it::

    python -m mcp.demo            # from the agentic-platform/ root
    python mcp/demo.py            # equivalently

Everything happens in one process over :class:`InProcessTransport`: no network,
no API keys, no spend. What you'll see:

1. the server **builds** with its three tools, a resource, and a prompt,
2. a guarded client **handshakes** and **discovers** the tools (with schemas),
3. it calls the **allow-listed** read tools (``search_docs``, ``get_ticket``),
4. the guards **refuse** the off-list write tool and a malformed call,
5. the allowed tools are exported as an **agent-loop toolset**.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run straight from a clone: put the agentic-platform/ root on the path so
# `import mcp` resolves to this package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import (  # noqa: E402
    InProcessTransport,
    SafeMCPClient,
    SafetyError,
    as_agent_tools,
    build_server,
)
from mcp.server import TOOL_SCOPES  # noqa: E402


def main() -> int:
    os.environ.setdefault("COMPANION_MOCK", "1")
    print("== capstone MCP demo (COMPANION_MOCK=1, in-process, no network) ==\n")

    server = build_server()  # MockMCPServer in MOCK mode
    transport = InProcessTransport(server)

    # A read-only client: allow only the two read tools; the write tool is denied.
    client = SafeMCPClient(transport, allow=["search_docs", "get_ticket"], timeout=5.0)
    client.initialize()
    print("handshake ok")

    tools = client.discover()
    print(f"discovered {len(tools)} tools: {', '.join(t.name for t in tools)}")
    print(f"declared scopes: {TOOL_SCOPES}")
    print(f"allow-listed: {sorted(client.allowed)}\n")

    print("search_docs(query='reset mfa')  ->", client.call("search_docs", {"query": "reset mfa"}))
    print("get_ticket(ticket_id='TICK-1001') ->", client.call("get_ticket", {"ticket_id": "TICK-1001"}))

    print("\n-- safety guards --")
    _expect_refusal("write tool off allow-list", lambda: client.call(
        "create_ticket", {"title": "x", "description": "y"}
    ))
    _expect_refusal("bad arguments", lambda: client.call("search_docs", {}))  # missing query

    toolset = as_agent_tools(client)
    print("\nagent toolset:", sorted(toolset))

    print("\nOK - server<->client round-trip complete, no API spend.")
    return 0


def _expect_refusal(label: str, thunk) -> None:  # noqa: ANN001
    try:
        thunk()
    except SafetyError as exc:
        print(f"refused ({label}): {type(exc).__name__}: {exc}")
    else:  # pragma: no cover - the guard should always fire here
        raise AssertionError(f"expected a refusal for: {label}")


if __name__ == "__main__":
    raise SystemExit(main())
