#!/usr/bin/env python3
"""Runnable demo — an in-process MCP server ↔ safe client round-trip, MOCK by default.

Run it::

    python demo.py

Everything happens in one process over :class:`InProcessTransport`: **no network, no API keys,
no spend.** ``COMPANION_MOCK`` defaults to ``1`` (the repo-wide offline switch); this blueprint
has no live path to gate, so MOCK simply documents intent and keeps parity with the notebooks.

What you'll see:

1. the client **handshakes** and **discovers** the server's tools (with schemas),
2. it calls an **allow-listed** tool successfully,
3. it **reads a resource**,
4. the four guards **refuse** an off-list tool and a malformed call,
5. the allowed tools are exported as an **agent-loop toolset** (``{name: callable}``).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run straight from a clone without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mcp_server import (  # noqa: E402
    InProcessTransport,
    SafeMCPClient,
    SafetyError,
    as_agent_tools,
    build_default_server,
)


def main() -> int:
    mock = os.getenv("COMPANION_MOCK", "1")
    print(f"== MCP server blueprint demo (COMPANION_MOCK={mock}, in-process, no network) ==\n")

    # --- expose: stand up a server with the example tools + resources ---------------------
    server = build_default_server(name="demo")
    transport = InProcessTransport(server)

    # --- consume: a guarded client, allow-listing only the two tools we trust -------------
    client = SafeMCPClient(transport, allow=["add", "echo"], timeout=5.0)
    client.initialize()
    print("handshake ok")

    tools = client.discover()
    print(f"discovered {len(tools)} tools: {', '.join(t.name for t in tools)}")
    print(f"allow-listed: {sorted(client.allowed)}\n")

    # 1) a successful, allow-listed call
    print("add(a=2, b=40)         ->", client.call("add", {"a": 2, "b": 40}))
    print("echo(text='hi there')  ->", client.call("echo", {"text": "hi there"}))

    # 2) read a read-only resource
    readme = transport.send(
        {"jsonrpc": "2.0", "id": 99, "method": "resources/read", "params": {"uri": "mem://readme"}}
    )
    snippet = readme["result"]["contents"][0]["text"].splitlines()[0]
    print("resources/read readme  ->", snippet, "\n")

    # 3) the guards refuse what they should
    print("-- safety guards --")
    _expect_refusal("off allow-list", lambda: client.call("now", {"format": "iso"}))
    _expect_refusal("bad arguments", lambda: client.call("add", {"a": 1}))  # missing 'b'

    # 4) hand the allowed tools to an agent loop as a {name: callable} toolset
    toolset = as_agent_tools(client)
    print("\nagent toolset:", sorted(toolset))
    print("toolset['add'](a=5, b=5) ->", toolset["add"](a=5, b=5))

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
