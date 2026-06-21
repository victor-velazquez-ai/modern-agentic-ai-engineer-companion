"""Read-mostly, least-privilege ops tools — exposed via the ``mcp-server`` pattern (Ch 19, 41).

This is where the *scoped tool surface* lives. The copilot does not get a shell. It gets a small
set of **named, schema-validated** tools served by a real :class:`mcp_server.MCPServer` and
consumed behind the :class:`mcp_server.SafeMCPClient` guardrails (allow-list, arg validation,
timeout). Nothing here is forked from the pattern — we import the pattern and register handlers.

The single most important design choice (Appendix G; Ch 41) is the **split**:

* :data:`READ_TOOLS` — observability/log/deploy *reads*: ``get_metrics``, ``search_logs``,
  ``list_deploys``, ``service_health``. These are safe to allow-list outright; the worst a
  read can do is be wrong, and the agent loop is built to recover from a wrong read.
* :data:`MUTATING_TOOLS` — production *mutations*: ``restart_service``, ``rollback_deploy``.
  These exist so the copilot can *propose* them, but they are **not** on the agent's allow-list.
  They run only through the human approval gate (see ``app/approve.py``). "Earned autonomy"
  means a verb moves from this set to the read set only after per-action evals justify it.

Everything is backed by an in-memory fixture so the whole tool surface runs **offline, with no
network and no keys** — the same MOCK posture as the rest of the repo. Swap the handlers for
your Datadog/Grafana/Loki/Kubernetes/Argo MCP servers and the shapes do not change.
"""

from __future__ import annotations

from typing import Any, Mapping

import _bootstrap  # noqa: F401  (wire the composed patterns onto sys.path)

from mcp_server import (  # noqa: E402  (after the path bootstrap)
    InProcessTransport,
    MCPServer,
    SafeMCPClient,
    Tool,
)

# --- The tool taxonomy -------------------------------------------------------------------
# READ_TOOLS are safe to allow-list. MUTATING_TOOLS are proposable but gated (never allow-listed
# for the agent). This list *is* the autonomy policy, in code — not a comment.
READ_TOOLS: tuple[str, ...] = ("get_metrics", "search_logs", "list_deploys", "service_health")
MUTATING_TOOLS: tuple[str, ...] = ("restart_service", "rollback_deploy")


# --- A tiny offline fixture of "production" state ----------------------------------------
# Deterministic so the demo and evals reproduce exactly. Keyed by service.
_METRICS: dict[str, dict[str, Any]] = {
    "checkout": {"error_rate": 0.42, "p99_latency_ms": 5200, "rps": 310, "cpu": 0.88},
    "payments": {"error_rate": 0.01, "p99_latency_ms": 240, "rps": 90, "cpu": 0.35},
    "search": {"error_rate": 0.03, "p99_latency_ms": 410, "rps": 540, "cpu": 0.51},
}

_LOGS: dict[str, list[str]] = {
    "checkout": [
        "ERROR pool exhausted: could not acquire db connection (waited 30000ms)",
        "ERROR upstream payments timeout after 30s",
        "WARN  connection pool at 100% utilization (size=20)",
        "ERROR HikariPool-1 - Connection is not available, request timed out",
    ],
    "payments": ["INFO  processed 90 charges in last minute", "INFO  healthcheck ok"],
    "search": ["WARN  slow query took 410ms", "INFO  index refreshed"],
}

_DEPLOYS: dict[str, list[dict[str, Any]]] = {
    "checkout": [
        {"id": "deploy-1042", "version": "v2.7.0", "at": "2026-06-20T13:55:00Z", "current": True},
        {"id": "deploy-1041", "version": "v2.6.4", "at": "2026-06-19T09:10:00Z", "current": False},
    ],
    "payments": [
        {"id": "deploy-0900", "version": "v5.1.2", "at": "2026-06-18T11:00:00Z", "current": True},
    ],
    "search": [
        {"id": "deploy-0500", "version": "v3.0.0", "at": "2026-06-17T08:00:00Z", "current": True},
    ],
}


def _service_arg(args: Mapping[str, Any]) -> str:
    service = str(args["service"]).strip().lower()
    return service


# --- Read handlers (safe) ----------------------------------------------------------------


def _get_metrics(args: Mapping[str, Any]) -> dict[str, Any]:
    service = _service_arg(args)
    return {"service": service, "metrics": _METRICS.get(service, {})}


def _search_logs(args: Mapping[str, Any]) -> dict[str, Any]:
    service = _service_arg(args)
    query = str(args.get("query", "")).lower()
    lines = _LOGS.get(service, [])
    if query:
        lines = [ln for ln in lines if query in ln.lower()]
    return {"service": service, "matches": lines, "count": len(lines)}


def _list_deploys(args: Mapping[str, Any]) -> dict[str, Any]:
    service = _service_arg(args)
    return {"service": service, "deploys": _DEPLOYS.get(service, [])}


def _service_health(args: Mapping[str, Any]) -> dict[str, Any]:
    service = _service_arg(args)
    m = _METRICS.get(service, {})
    err = float(m.get("error_rate", 0.0))
    status = "critical" if err >= 0.2 else "degraded" if err >= 0.05 else "healthy"
    return {"service": service, "status": status, "error_rate": err}


# --- Mutating handlers (proposable, but GATED — never on the agent allow-list) -----------


def _restart_service(args: Mapping[str, Any]) -> dict[str, Any]:
    # In MOCK mode this only records that the (approved) action "happened"; a real handler would
    # call the orchestrator. It is wired into the server so an *approved* call has somewhere to go.
    service = _service_arg(args)
    return {"service": service, "action": "restart_service", "result": "restarted (mock)"}


def _rollback_deploy(args: Mapping[str, Any]) -> dict[str, Any]:
    service = _service_arg(args)
    to = str(args.get("to_version", "previous"))
    return {"service": service, "action": "rollback_deploy", "to_version": to, "result": "rolled back (mock)"}


_SERVICE_SCHEMA = {
    "type": "object",
    "properties": {"service": {"type": "string", "maxLength": 64}},
    "required": ["service"],
    "additionalProperties": False,
}


def _read_tools() -> list[Tool]:
    return [
        Tool(
            name="get_metrics",
            description="Read current metrics (error rate, p99 latency, rps, cpu) for a service.",
            input_schema=_SERVICE_SCHEMA,
            handler=_get_metrics,
        ),
        Tool(
            name="search_logs",
            description="Search recent log lines for a service, optionally filtered by a substring.",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "maxLength": 64},
                    "query": {"type": "string", "maxLength": 200},
                },
                "required": ["service"],
                "additionalProperties": False,
            },
            handler=_search_logs,
        ),
        Tool(
            name="list_deploys",
            description="List recent deploys for a service (id, version, time, which is current).",
            input_schema=_SERVICE_SCHEMA,
            handler=_list_deploys,
        ),
        Tool(
            name="service_health",
            description="Summarize a service's health as healthy / degraded / critical.",
            input_schema=_SERVICE_SCHEMA,
            handler=_service_health,
        ),
    ]


def _mutating_tools() -> list[Tool]:
    return [
        Tool(
            name="restart_service",
            description="Restart a service. MUTATES PRODUCTION — requires human approval.",
            input_schema=_SERVICE_SCHEMA,
            handler=_restart_service,
        ),
        Tool(
            name="rollback_deploy",
            description="Roll a service back to a previous version. MUTATES PRODUCTION — requires approval.",
            input_schema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "maxLength": 64},
                    "to_version": {"type": "string", "maxLength": 64},
                },
                "required": ["service"],
                "additionalProperties": False,
            },
            handler=_rollback_deploy,
        ),
    ]


def build_ops_server(*, include_mutating: bool = True) -> MCPServer:
    """A real :class:`mcp_server.MCPServer` pre-loaded with the ops tools.

    ``include_mutating`` controls whether the server even *exposes* the mutating verbs. The
    server can host them (so an approved action has a handler to reach), but — see
    :func:`build_ops_client` — they are never added to the *agent's* allow-list.
    """
    server = MCPServer(name="ops")
    for t in _read_tools():
        server.add_tool(t)
    if include_mutating:
        for t in _mutating_tools():
            server.add_tool(t)
    return server


def build_ops_client(*, allow_mutating: bool = False) -> SafeMCPClient:
    """A discovered, initialized :class:`mcp_server.SafeMCPClient` over the ops server.

    By default **only the read tools are allow-listed** — least privilege, deny-by-default. The
    mutating verbs are discoverable (the copilot can *see* they exist, to propose them) but not
    callable through this client. ``allow_mutating=True`` exists only for the approval gate to
    construct a *separately scoped* client once a human has signed off; the agent never gets one.
    """
    server = build_ops_server(include_mutating=True)
    client = SafeMCPClient(InProcessTransport(server))
    client.initialize()
    client.discover()
    for name in READ_TOOLS:
        client.allow_tool(name)
    if allow_mutating:
        for name in MUTATING_TOOLS:
            client.allow_tool(name)
    return client
