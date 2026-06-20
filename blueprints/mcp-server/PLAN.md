# Blueprint — MCP Server  (pattern)

> Realizes book Ch 19 · mirrors capstone `mcp/` · Status: 📋 planned (Phase 1)

## What it is
A small **Model Context Protocol server** that exposes a few tools and resources over MCP, *plus*
the **safe-consumption** side: an MCP client that discovers and calls a server's tools with the
guardrails you want before letting a model drive third-party tools (allow-list, argument
validation, timeouts, least privilege). The standalone reference for both ends of MCP.

## Why a blueprint (not a notebook)
- MCP is a wire protocol with a server lifecycle; a notebook can narrate it, but a *runnable*
  server + client pair is the only honest way to show transport, discovery, and invocation.
- Solution blueprints (sales/RevOps) expose capabilities **through** an MCP server, so a stable,
  tested server skeleton is worth lifting.
- The safety story — "never hand a remote tool to the model unfiltered" — is enforced in code
  (the consumption guards), not described.

## Planned structure
```text
mcp-server/
├── README.md                  # MCP in one diagram, expose vs. consume, safety trade-offs, adapt
├── pyproject.toml
├── src/mcp_server/
│   ├── __init__.py
│   ├── server.py              #   the MCP server: register tools + resources, lifecycle
│   ├── tools.py               #   example tool implementations (pure, schema'd)
│   ├── resources.py           #   example read-only resources exposed over MCP
│   └── consume.py             #   safe MCP client: discover, allow-list, validate, timeout
├── tests/
│   ├── test_server.py         #   tool/resource registration + handshake
│   ├── test_consume.py        #   client discovers tools and invokes one
│   └── test_safety.py         #   non-allow-listed tool / bad args are refused
└── demo.py                    # runnable: in-process server + client round-trip, MOCK transport
```

## Composes / depends on
- **`agent-loop`** — the consumption side feeds discovered MCP tools into a loop's toolset
  (an agent driving MCP tools), so it composes with the loop's tool protocol.
- Otherwise **foundational** for the MCP capability; uses an in-process/stdio transport so it
  runs with no network and no keys.

## Maps to the book
- **Ch 19 — MCP & Tool Ecosystems:** building an MCP server (tools + resources), the protocol
  lifecycle, and consuming external MCP servers safely. Makes §19's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-05-architectures-and-orchestration/19-mcp-and-tool-ecosystems/`](../../learn/part-05-architectures-and-orchestration/19-mcp-and-tool-ecosystems/)
  builds and consumes an MCP server in isolation and **ends by pointing here**.

## Maps to the capstone
Standalone version of capstone **`mcp/`** — the MCP server exposing the platform's tools (Ch 19),
plus the safe client the capstone's agents use to reach external MCP tools.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; registration, discovery/invocation, and safety refusals covered.
- [ ] `python demo.py` runs a server↔client round-trip in **`MOCK=1`** (in-process transport, no
      network, no API spend).
- [ ] README explains trade-offs: expose-vs-consume, transport choices, and the consumption
      guardrails (allow-list, validation, timeout, least privilege).
- [ ] Cross-links (`agent-loop`, the Ch 19 walkthrough, capstone `mcp/`) resolve.
