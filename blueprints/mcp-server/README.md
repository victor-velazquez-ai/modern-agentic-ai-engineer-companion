# 🔌 Blueprint — MCP Server (pattern)

> Realizes book **Ch 19 — MCP & Tool Ecosystems** · standalone version of capstone [`mcp/`](../../capstone/) · Status: ✅ built

A small **Model Context Protocol** server that exposes tools and resources, *plus* the
**safe-consumption** side: an MCP client that discovers a server's tools and calls them behind
the guardrails you want before letting a model drive third-party tools. Both ends run **in one
process, with no network and no API keys** — you read this blueprint by *running* it.

```bash
python demo.py            # in-process server ↔ safe client round-trip (MOCK, free)
pytest tests/             # registration · discovery/invocation · safety refusals
```

---

## MCP in one diagram

```text
                  ┌──────────────────────────── your process ────────────────────────────┐
   model / agent  │   SafeMCPClient ──guards──▶  Transport  ──▶  MCPServer                │
   (agent-loop)   │   ┌─────────────┐            (the seam)      ┌──────────────────────┐ │
        │         │   │ allow-list  │                            │ tools/   (verbs)     │ │
        └── tools ◀───│ validate    │   initialize ─────────────▶│ resources/ (nouns,   │ │
            {name:fn} │ timeout     │   tools/list  ◀────────────│            read-only)│ │
                  │   │ least-priv  │   tools/call  ─────────────▶│ lifecycle + dispatch │ │
                  │   └─────────────┘   resources/read ──────────▶└──────────────────────┘ │
                  └───────────────────────────────────────────────────────────────────────┘
                      ▲ consume side                                ▲ expose side
```

The **Transport** is the only thing that changes between offline and production. Here it's
[`InProcessTransport`](src/mcp_server/server.py) (a method call). Swap in stdio or HTTP+SSE and
nothing above the `send(request) -> response` seam moves.

---

## What's in here

| File | Role |
|---|---|
| [`src/mcp_server/server.py`](src/mcp_server/server.py) | The MCP server: registers tools + resources, owns the `initialize → list → call` **lifecycle**, dispatches JSON-RPC-shaped requests, and turns failures into structured errors (never crashes the transport). Ships `InProcessTransport`. |
| [`src/mcp_server/tools.py`](src/mcp_server/tools.py) | The `Tool` type — name, description, JSON-Schema-subset `input_schema`, and a **pure** handler. Plus `validate_args`, the dependency-free validator both ends share. Example tools: `add`, `echo`, `now`. |
| [`src/mcp_server/resources.py`](src/mcp_server/resources.py) | `Resource` — read-only, URI-addressed context (a doc, a config blob). Exposing a resource can never mutate state. |
| [`src/mcp_server/consume.py`](src/mcp_server/consume.py) | `SafeMCPClient` — discover, then call **only** what's allow-listed, validated, and under a timeout. `as_agent_tools()` exports the allowed set as an `agent-loop` toolset. |
| [`tests/`](tests/) | `test_server.py` (registration + handshake), `test_consume.py` (discovery + invocation), `test_safety.py` (refusals). |
| [`demo.py`](demo.py) | The runnable round-trip. |

---

## Expose vs. consume — and the safety trade-offs

**Exposing** (the server) is the easy half: register typed tools and read-only resources, answer
the protocol. The judgment is in **keeping tools pure and schema'd** and **resources read-only**,
so a client can validate calls and can never mutate through a read.

**Consuming** (the client) is where teams get hurt. A remote MCP server is third-party code you
don't control: its tool list can change between sessions, its schemas can be wrong or adversarial,
and one unfiltered tool is a prompt-injection surface straight into your agent. So the
consumption side is **guarded in code, not in a doc** — four guards, every call:

1. **Allow-list (least privilege).** Default is **deny**. Discovery can *see* every tool;
   only names you explicitly allow are callable. A server that quietly adds `delete_all` later
   can never reach the model — see `test_server_adding_a_dangerous_tool…` in
   [`tests/test_safety.py`](tests/test_safety.py).
2. **Argument validation** against the *discovered* schema, **locally, before the wire** — bad
   calls fail fast with a clear message and zero round-trips.
3. **Per-call timeout** — a slow or hung server can't stall the agent.
4. **No ambient authority** — the client holds only a transport and its allow-list; it grants
   nothing it wasn't handed.

| Choice | Cheap & safe (here) | When you'd change it |
|---|---|---|
| **Transport** | in-process (no net, no keys) | stdio for a local subprocess server; HTTP+SSE for a remote one — same seam |
| **Trust** | named allow-list per tool | `allow_all_discovered()` only for **in-house** servers you version together |
| **Validation** | JSON-Schema subset, stdlib | full JSON-Schema / `pydantic` models for richer contracts |
| **Schemas** | declared on the tool | generated from typed signatures in a larger codebase |

---

## Composes with `agent-loop`

The consumption side is built to feed an agent loop. `as_agent_tools(client)` returns exactly the
toolset shape a loop consumes — `{name: callable}` — with every guard already applied:

```python
from mcp_server import SafeMCPClient, InProcessTransport, build_default_server, as_agent_tools

client = SafeMCPClient(InProcessTransport(build_default_server()), allow=["add", "echo"])
client.initialize(); client.discover()

toolset = as_agent_tools(client)        # {"add": <callable>, "echo": <callable>}, guarded
# hand `toolset` to ../agent-loop/ as the loop's tools — the agent now drives MCP tools safely.
```

See [`../agent-loop/`](../agent-loop/) for the loop that consumes this toolset. This blueprint is
otherwise **foundational**: it needs no other blueprint and no keys to run.

---

## How to adapt

- **Real tools:** replace the handlers in `tools.py`; keep them pure and keep the schema accurate
  (the schema *is* the contract the client validates against).
- **Real resources:** back `Resource.read()` with files / a DB / an API; keep it read-only.
- **Real transport:** implement the `Transport` protocol (`send(request) -> response`) over stdio
  or HTTP+SSE. Server logic and client guards are unchanged.
- **Richer validation:** swap the schema subset for full JSON-Schema or `pydantic`; `validate_args`
  is the single choke point.

---

## Links

- **Book:** Ch 19 — MCP & Tool Ecosystems (the 🔧 Build sections).
- **Walkthrough that points here:** [`../../learn/part-05-architectures-and-orchestration/19-mcp-and-tool-ecosystems/`](../../learn/part-05-architectures-and-orchestration/19-mcp-and-tool-ecosystems/)
- **Composes:** [`../agent-loop/`](../agent-loop/) (drives the discovered tools).
- **Capstone:** standalone version of [`../../capstone/`](../../capstone/) `mcp/`.
- **Standards:** [`../../docs/NOTEBOOK-STANDARDS.md`](../../docs/NOTEBOOK-STANDARDS.md) (MOCK / safety / output hygiene).
