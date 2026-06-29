# `mcp/` — MCP server exposing platform tools (Ch 19)

The platform's tool infrastructure, published over the **Model Context Protocol**.
A `FastMCP` server exposes the capstone's *enterprise* tools (document search,
ticket lookup/create), one read-only resource, and one prompt — plus the
**safe-consumption** side that lets the agent loop drive an MCP server behind
guardrails. Both ends run **in one process, with no network and no API keys**.

> Built in **Chapter 19 — MCP & Tool Ecosystems** (§19 Build). Standalone pattern:
> [`blueprints/mcp-server/`](../../../blueprints/mcp-server/). This `mcp/` is the
> capstone-integrated version of that blueprint.

```bash
# from agentic-platform/
python -m mcp.demo     # server ↔ safe client round-trip (MOCK, free)
```

## What's exposed

| Primitive | Name | Backed by | Scope (for `security/`) |
|---|---|---|---|
| tool | `search_docs(query, top_k)` | `rag/` retriever (mock here) | `docs:read` |
| tool | `get_ticket(ticket_id)` | ticket tracker (mock here) | `tickets:read` |
| tool | `create_ticket(title, description, priority)` | ticket tracker (mock here) | `tickets:write` |
| resource | `runbook://{name}` | in-repo runbooks | — (read-only) |
| prompt | `triage(ticket_id)` | — | — |

The three MCP primitives, and *who controls use*: **tools** (the model calls),
**resources** (the app attaches to context, read-only), **prompts** (the user
invokes). FastMCP turns each function's **type hints + docstring into the JSON
schema** clients discover — write the function, get the contract.

## Files

| File | Role |
|---|---|
| [`server.py`](server.py) | `build_server()` registers the three tools, the `runbook` resource, and the `triage` prompt on a `FastMCP("capstone-enterprise")` instance — or a mock fallback. Declares `TOOL_SCOPES`. |
| [`backends.py`](backends.py) | The seams the tools call: a `DocSearch` protocol (satisfied by `rag/` in production, `MockDocSearch` here) and a `TicketTracker` protocol (a tracker adapter / `MockTicketTracker` here). Deterministic, offline. |
| [`mock_server.py`](mock_server.py) | An in-process server with a FastMCP-compatible decorator API + `InProcessTransport`. The `MOCK`/offline path; answers `initialize`, `tools/list`, `tools/call`, `resources/read`, `prompts/get`, … |
| [`consume.py`](consume.py) | `SafeMCPClient` — discover, then call only what's allow-listed, validated, and under a timeout. `as_agent_tools()` exports the allowed set as the loop's `{name: callable}` toolset. |
| [`demo.py`](demo.py) | The runnable round-trip. |

## MOCK vs. real

`build_server()` returns the real `FastMCP` instance when the `mcp` package is
installed **and** `COMPANION_MOCK` is unset; otherwise an in-process
`MockMCPServer` with the identical tool/resource/prompt surface. The registration
logic in `server.py` is the single source of truth either way — only the
framework object differs.

```bash
pip install "mcp[cli]"          # the real FastMCP runtime
COMPANION_MOCK= python -m mcp.server     # serve over stdio (or Streamable HTTP)
```

**Transport is a seam.** In MOCK mode the round-trip is a method call
(`InProcessTransport`). For real, `FastMCP` speaks **stdio** by default and
**Streamable HTTP** for a networked deployment — the same server object, a
different transport, nothing above it changes.

## Security boundaries (the part most tutorials skip)

Consumption is **guarded in code, not in a doc** — four guards on every call in
[`consume.py`](consume.py):

1. **Allow-list (least privilege).** Default deny. The demo allow-lists only the
   read tools; `create_ticket` (`tickets:write`) is refused even though it's
   discovered — a server that later adds a dangerous tool can't reach the model.
2. **Argument validation** against the *discovered* schema, locally, before the
   wire.
3. **Per-call timeout** — a slow/hung server can't stall the agent.
4. **No ambient authority** — the client holds only a transport and its
   allow-list.

`TOOL_SCOPES` in `server.py` is the declaration; the `security/` policy layer
maps a caller's granted scopes to the tools it may invoke. Declaring scopes next
to the tools keeps the permission surface in one reviewable place.

## How it wires into the platform

- `search_docs` → `rag/` (the `Retriever` protocol). Here `MockDocSearch` scores
  a tiny fixed corpus so retrieval is deterministic and keyless.
- `get_ticket` / `create_ticket` → a ticket-tracker adapter under `app/services/`
  in the full build. Here `MockTicketTracker` is in-memory with deterministic ids.
- `as_agent_tools(client)` → the `{name: callable}` toolset `agents/raw/` consumes
  — every call already guarded.

Swap the mock backends in `backends.py` for real adapters and **nothing in
`server.py` or `consume.py` changes** — that's the seam the capstone leans on.
