"""Scoped support/billing tools, exposed over MCP (Ch 19) — the *act* surface.

The agent's ability to *act* (reset a password, issue an in-policy refund, change a plan,
check an order) is exactly the part you must keep on a short leash. This module models that
the way a senior would: the actions live behind the ``mcp-server`` pattern blueprint, so the
agent reaches them only through the **safe consumption boundary** — discovery, an allow-list,
argument validation against each tool's declared schema, and a per-call timeout.

Two deliberate boundaries are drawn here:

* **Read vs. write.** ``order_status`` and ``account_lookup`` are read-only and cheap to allow.
  ``reset_password`` and ``change_plan`` are reversible writes. ``issue_refund`` moves money —
  it is the one tool the escalation policy gates by amount (see ``app/policies.py``).
* **Least privilege at the client.** :func:`build_support_client` allow-lists *only* the tools
  the autonomy dial currently enables. Discovery still *sees* every tool, but an off-list tool
  (or one a future server quietly adds) can never reach the loop — the deny-by-default guard in
  ``SafeMCPClient`` refuses it.

Everything is an **in-process** MCP round-trip (``InProcessTransport``): no network, no keys, no
spend. Swap the handlers for calls into your real billing/CRM system and swap the transport for
stdio/HTTP — nothing above the transport changes. This module forks nothing; it builds on the
published ``mcp_server`` package made importable by :mod:`app._paths`.
"""

from __future__ import annotations

# Make the sibling pattern blueprints importable (side effect) before we import them.
from app import _paths  # noqa: F401

from typing import Any, Mapping

from mcp_server import (
    InProcessTransport,
    MCPServer,
    SafeMCPClient,
    Tool,
)

# --- A tiny in-memory "billing system" the tools act on ------------------------------------
#
# In a real deployment these reads/writes hit your CRM, billing, and auth systems. Here they
# mutate a dict so the demo is self-contained and deterministic. The *shapes* (a customer
# record, an order, a refund receipt) are what a real integration preserves.

_ACCOUNTS: dict[str, dict[str, Any]] = {
    "cus_001": {"email": "ada@example.com", "plan": "pro", "status": "active"},
    "cus_002": {"email": "grace@example.com", "plan": "starter", "status": "active"},
}

_ORDERS: dict[str, dict[str, Any]] = {
    "ord_1001": {"customer": "cus_001", "status": "shipped", "eta": "2026-06-24"},
    "ord_1002": {"customer": "cus_002", "status": "processing", "eta": "2026-06-27"},
}

_VALID_PLANS = ("starter", "pro", "enterprise")


# --- Handlers (pure functions over already-validated args) ---------------------------------


def _account_lookup(args: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only: fetch a customer's account record (no PII beyond what support needs)."""
    customer_id = args["customer_id"]
    record = _ACCOUNTS.get(customer_id)
    if record is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, "customer_id": customer_id, **record}


def _order_status(args: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only: look up an order's fulfilment status and ETA."""
    order_id = args["order_id"]
    order = _ORDERS.get(order_id)
    if order is None:
        return {"found": False, "order_id": order_id}
    return {"found": True, "order_id": order_id, **order}


def _reset_password(args: Mapping[str, Any]) -> dict[str, Any]:
    """Reversible write: trigger a password-reset email (no secret is returned)."""
    customer_id = args["customer_id"]
    if customer_id not in _ACCOUNTS:
        return {"ok": False, "reason": "unknown customer"}
    # A real system enqueues an email; here we just confirm the side effect's shape.
    return {"ok": True, "customer_id": customer_id, "action": "reset_email_sent"}


def _change_plan(args: Mapping[str, Any]) -> dict[str, Any]:
    """Reversible write: move a customer between subscription plans."""
    customer_id = args["customer_id"]
    new_plan = args["new_plan"]
    record = _ACCOUNTS.get(customer_id)
    if record is None:
        return {"ok": False, "reason": "unknown customer"}
    previous = record["plan"]
    record["plan"] = new_plan
    return {"ok": True, "customer_id": customer_id, "from": previous, "to": new_plan}


def _issue_refund(args: Mapping[str, Any]) -> dict[str, Any]:
    """Irreversible write (money leaves): issue a refund.

    The *amount gate* does not live here — that is policy, and it lives in ``app/policies.py``
    so it can be tuned per domain and targeted by the eval set. This handler assumes the caller
    already cleared the gate; it records the receipt. Defence-in-depth: a real system would also
    enforce a hard ceiling server-side, independent of the agent.
    """
    customer_id = args["customer_id"]
    amount = float(args["amount_usd"])
    if customer_id not in _ACCOUNTS:
        return {"ok": False, "reason": "unknown customer"}
    return {
        "ok": True,
        "customer_id": customer_id,
        "amount_usd": round(amount, 2),
        "receipt": f"rfnd_{customer_id}_{int(amount * 100)}",
    }


# --- Tool definitions (name, JSON-Schema, handler) -----------------------------------------
#
# The schema is the contract the safe client validates against *before* a call reaches the
# wire — so a malformed tool call from the model fails fast, locally, with a clear message.


def build_support_tools() -> list[Tool]:
    """The scoped support/billing toolset this solution exposes over MCP."""
    return [
        Tool(
            name="account_lookup",
            description="Read-only: fetch a customer's account (email, plan, status).",
            input_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string", "minLength": 1}},
                "required": ["customer_id"],
                "additionalProperties": False,
            },
            handler=_account_lookup,
        ),
        Tool(
            name="order_status",
            description="Read-only: look up an order's fulfilment status and ETA.",
            input_schema={
                "type": "object",
                "properties": {"order_id": {"type": "string", "minLength": 1}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
            handler=_order_status,
        ),
        Tool(
            name="reset_password",
            description="Send a password-reset email to a customer (reversible).",
            input_schema={
                "type": "object",
                "properties": {"customer_id": {"type": "string", "minLength": 1}},
                "required": ["customer_id"],
                "additionalProperties": False,
            },
            handler=_reset_password,
        ),
        Tool(
            name="change_plan",
            description="Change a customer's subscription plan (reversible).",
            input_schema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "minLength": 1},
                    "new_plan": {"type": "string", "enum": list(_VALID_PLANS)},
                },
                "required": ["customer_id", "new_plan"],
                "additionalProperties": False,
            },
            handler=_change_plan,
        ),
        Tool(
            name="issue_refund",
            description=(
                "Issue a refund to a customer (IRREVERSIBLE — money leaves). "
                "The amount gate is enforced by the escalation policy, not here."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "minLength": 1},
                    "amount_usd": {"type": "number", "minimum": 0},
                },
                "required": ["customer_id", "amount_usd"],
                "additionalProperties": False,
            },
            handler=_issue_refund,
        ),
    ]


# The tools the autonomy dial currently enables. Start small; add a name here only after the
# eval set shows the agent matches human decisions for that action type (PLAN.md → autonomy dial).
# Note: ``issue_refund`` IS allow-listed, but every refund still passes the amount gate in
# ``app/policies.py`` first — least privilege at the boundary *and* a policy gate above it.
DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "account_lookup",
    "order_status",
    "reset_password",
    "change_plan",
    "issue_refund",
)


def build_support_server(name: str = "support-billing") -> MCPServer:
    """An in-process MCP server exposing the scoped support/billing tools."""
    server = MCPServer(name=name)
    for tool in build_support_tools():
        server.add_tool(tool)
    return server


def build_support_client(
    *,
    allow: tuple[str, ...] = DEFAULT_ALLOWED_TOOLS,
    timeout: float = 5.0,
) -> SafeMCPClient:
    """Stand up the server + a *guarded* client, handshake, discover, and return the client.

    The returned client has already performed the MCP handshake and discovery, so its allowed
    tools are immediately usable as an agent toolset (``mcp_server.as_agent_tools``). A tool not
    in ``allow`` is discoverable but never callable — the deny-by-default guard refuses it.
    """
    server = build_support_server()
    transport = InProcessTransport(server)
    client = SafeMCPClient(transport, allow=allow, timeout=timeout)
    client.initialize()
    client.discover()
    return client
