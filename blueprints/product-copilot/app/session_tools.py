"""Session-scoped tools — the agent acts **as the signed-in user**, never as a service (Ch 12/41).

The defining safety property of a customer-facing copilot (PLAN.md, Ch 43): every action the
agent takes is scoped to the authenticated *(tenant, user)* session. There is no privileged
service identity anywhere in the request path. A tool that lists "my orders" lists *this user's*
orders in *this user's* tenant — it is structurally incapable of reading anyone else's, because
the only identity it can see is the :class:`~tenancy.Session` it was bound with.

How that property is enforced here:

* A tool is built by :func:`build_session_tools`, which **closes over** one ``Session``. The
  ``agent_loop`` model never sees ``user_id`` / ``tenant_id`` as arguments it could spoof — they
  are baked into the closure from the *verified* session, not the prompt. (This is the seam the
  PLAN insists on: "tools act ONLY as the authenticated user".)
* Every read goes through :class:`UserDataStore`, which filters by ``(tenant_id, user_id)`` first
  and returns nothing for any other identity — deny-by-default, the same posture
  ``tenancy.scope`` takes for retrieval.

We compose the ``agent-loop`` blueprint's :class:`~agent_loop.ToolRegistry` and ``@tool``
decorator — the exact dispatch/repair/recovery machinery the book hardens in Ch 12 — rather than
re-implementing tool calling. The data store is an in-memory mock (no deps, no network, $0); swap
it for your product's real per-user API and keep the *bind-to-session* shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import _compose  # noqa: F401  (side effect: pattern blueprints on sys.path)

from agent_loop import Tool, ToolError, ToolRegistry, tool  # type: ignore  # noqa: E402

from tenancy import Session  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# A tiny, mock per-user data store (stands in for your product's real API)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Order:
    """One order belonging to a single user within a single tenant."""

    order_id: str
    status: str
    total_usd: float


@dataclass(frozen=True)
class Account:
    """The user's account record (plan, seats) — read-only in this demo."""

    plan: str
    seats: int
    notifications: bool = True


@dataclass
class UserDataStore:
    """An in-memory, *tenant-and-user-scoped* mock of the product's own data plane.

    Every row is keyed by ``(tenant_id, user_id)``. The public methods take a :class:`Session`
    and return **only** that session's rows; there is deliberately **no** method that accepts an
    arbitrary tenant/user, so a tool built from a session cannot widen its own scope.

    This is the surface the PLAN calls "answering questions about their own data in the app" —
    here as deterministic fixtures so the demo runs offline. Replace the dicts with calls to your
    real per-user service; keep the "session in, only-their-rows out" contract.
    """

    _orders: dict[tuple[str, str], list[Order]] = field(default_factory=dict)
    _accounts: dict[tuple[str, str], Account] = field(default_factory=dict)
    # An append-only audit of mutations, for the demo / observability (who changed what).
    audit: list[dict[str, Any]] = field(default_factory=list)

    def _key(self, session: Session) -> tuple[str, str]:
        return (session.tenant_id, session.user_id)

    # -- seeding (used by the demo's fixtures) ----------------------------------------
    def seed_orders(self, session: Session, orders: list[Order]) -> None:
        self._orders[self._key(session)] = list(orders)

    def seed_account(self, session: Session, account: Account) -> None:
        self._accounts[self._key(session)] = account

    # -- scoped reads -----------------------------------------------------------------
    def orders_for(self, session: Session) -> list[Order]:
        """This session's orders only (empty list for any other identity)."""
        return list(self._orders.get(self._key(session), []))

    def order(self, session: Session, order_id: str) -> Order | None:
        """One order by id, but only if it belongs to this session's user+tenant."""
        for o in self.orders_for(session):
            if o.order_id == order_id:
                return o
        return None

    def account_for(self, session: Session) -> Account | None:
        return self._accounts.get(self._key(session))

    # -- scoped write (a low-risk, in-policy account change) --------------------------
    def set_notifications(self, session: Session, enabled: bool) -> Account:
        """Flip the notification preference for **this** user only.

        A deliberately *reversible, low-risk* action — the kind the autonomy dial enables first.
        Irreversible/out-of-policy actions (delete account, transfer ownership, refunds over a
        limit) belong behind a human approval gate, not in an autonomously-callable tool.
        """
        account = self.account_for(session)
        if account is None:
            raise ToolError("no account on file for this user")
        updated = Account(
            plan=account.plan, seats=account.seats, notifications=enabled
        )
        self._accounts[self._key(session)] = updated
        self.audit.append(
            {"tenant": session.tenant_id, "user": session.user_id,
             "action": "set_notifications", "value": enabled}
        )
        return updated


# ---------------------------------------------------------------------------
# Build the agent's tools, bound to one session
# ---------------------------------------------------------------------------


def build_session_tools(session: Session, store: UserDataStore) -> ToolRegistry:
    """Return a :class:`~agent_loop.ToolRegistry` whose tools act **only** as ``session``.

    The session is captured in each tool's closure, so the model can call ``get_my_orders`` /
    ``get_order_status`` / ``set_notifications`` *without ever supplying an identity*. The model
    cannot ask for "tenant=acme, user=root"; the identity is fixed to the verified session. That
    is the whole point — a public model surface must not be trusted to name whose data it touches.

    Tools raise :class:`~agent_loop.ToolError` with a friendly message on a clean failure (e.g.
    an order id this user doesn't own); the agent loop turns that into a result the model can read
    and recover from, never a crash.
    """

    @tool(
        "get_my_orders",
        "List the signed-in user's own orders (id, status, total). Takes no arguments.",
        {"type": "object", "properties": {}},
    )
    def get_my_orders() -> str:
        orders = store.orders_for(session)
        if not orders:
            return "You have no orders on file."
        lines = [f"{o.order_id}: {o.status} (${o.total_usd:.2f})" for o in orders]
        return "Your orders:\n" + "\n".join(lines)

    @tool(
        "get_order_status",
        "Look up the status of one of the signed-in user's orders by its order id.",
        {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "An order id you own."}
            },
            "required": ["order_id"],
        },
    )
    def get_order_status(order_id: str) -> str:
        order = store.order(session, order_id)
        if order is None:
            # Note: identical message whether the order doesn't exist or belongs to another
            # tenant — never confirm the existence of data outside the user's scope.
            raise ToolError(
                f"no order {order_id!r} found on your account"
            )
        return f"Order {order.order_id} is {order.status} (total ${order.total_usd:.2f})."

    @tool(
        "set_notifications",
        "Turn the signed-in user's email notifications on or off (a reversible account change).",
        {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "True to enable, False to disable."}
            },
            "required": ["enabled"],
        },
    )
    def set_notifications(enabled: bool) -> str:
        account = store.set_notifications(session, enabled)
        state = "on" if account.notifications else "off"
        return f"Email notifications are now {state}."

    return ToolRegistry([get_my_orders, get_order_status, set_notifications])


__all__ = [
    "Order",
    "Account",
    "UserDataStore",
    "build_session_tools",
]
