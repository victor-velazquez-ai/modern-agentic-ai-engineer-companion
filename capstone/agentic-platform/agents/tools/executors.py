"""Safe executors: the platform's concrete tools, each with a declared risk tier (Ch 12, 19, 20).

These are the real tool *functions* the agents call, paired with the schema the model reads and
the :class:`~agents.tools.schemas.RiskTier` the approval gate enforces. "Safe executor" is the
operative word: every tool here is written so a model — possibly steered by a prompt injection —
cannot use it to do something the platform did not intend.

* ``calculator`` is a **bounded arithmetic evaluator**, *not* :func:`eval`. It parses an AST and
  permits only numeric literals and the four arithmetic operators, so ``__import__('os')`` can't
  ride in through a math tool. (The Ch 12 lesson: never hand model output to ``eval``.)
* ``search_docs`` is the seam to the ``rag/`` retriever — read-only, the safe default tier. The
  platform wires the real :class:`Retriever` here; the offline fallback returns canned hits so the
  agents run with no vector store.
* ``create_ticket`` writes platform-owned state (``WRITE``); ``send_email`` acts on the outside
  world (``EXTERNAL``) and so is gated by the approval policy by default.

The tools live behind :func:`default_toolset`, the registry an agent is handed. Confine a worker
to a subset with :meth:`ToolRegistry.subset` (capability confinement, Ch 17).
"""

from __future__ import annotations

import ast
import operator
from datetime import datetime, timezone
from typing import Any, Callable

from .schemas import RiskTier, Tool, ToolError, ToolRegistry, tool

# ---------------------------------------------------------------------------------------------
# calculator — a *safe* arithmetic evaluator (never eval())
# ---------------------------------------------------------------------------------------------

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate a *whitelisted* arithmetic AST node. Anything else is rejected."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ToolError(
        "calculator only supports +, -, *, /, %, ** on numbers; "
        f"unsupported expression element: {type(node).__name__}."
    )


def calculate(expression: str) -> str:
    """Evaluate a numeric arithmetic expression safely. Returns the result as a string."""
    if not isinstance(expression, str) or not expression.strip():
        raise ToolError("expression must be a non-empty string.")
    if len(expression) > 200:
        raise ToolError("expression too long.")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"could not parse expression: {exc.msg}.") from exc
    try:
        value = _eval_node(tree)
    except ZeroDivisionError as exc:
        raise ToolError("division by zero.") from exc
    # Render integers without a trailing .0 so the model reads "5" not "5.0".
    return str(int(value)) if value == int(value) else str(value)


# ---------------------------------------------------------------------------------------------
# clock — a trivial read-only tool
# ---------------------------------------------------------------------------------------------


def now(timezone_name: str = "UTC") -> str:
    """Return the current UTC time as an ISO-8601 string (the platform clock is UTC)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------------------------
# search_docs — the seam to rag/  (read-only)
# ---------------------------------------------------------------------------------------------

# A retriever takes a query (and a result count) and returns ranked text hits. The platform's
# ``rag/`` package satisfies this; here we accept any callable so the tool stays decoupled.
Retriever = Callable[[str, int], list[str]]


def _offline_retriever(query: str, k: int) -> list[str]:
    """Deterministic offline stand-in for ``rag/``: canned hits, no vector store, no network."""
    snippet = query.strip()[:60]
    return [f"[doc {i + 1}] relevant passage about '{snippet}'." for i in range(min(k, 3))]


def make_search_docs(retriever: Retriever | None = None) -> Tool:
    """Build the ``search_docs`` tool, wiring in a real ``rag/`` retriever (or the offline stub).

    Pass the platform's :class:`Retriever` to query the live corpus; omit it to run free with the
    canned retriever. Read-only, so the tool is :class:`RiskTier.READ` and never gated.
    """
    retrieve = retriever or _offline_retriever

    @tool(
        "search_docs",
        "Search the private document corpus and return the most relevant passages.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."},
                "k": {"type": "integer", "description": "How many passages to return (default 3)."},
            },
            "required": ["query"],
        },
        risk=RiskTier.READ,
    )
    def search_docs(query: str, k: int = 3) -> str:
        if not query or not query.strip():
            raise ToolError("query must be a non-empty string.")
        hits = retrieve(query, max(1, min(int(k), 10)))
        if not hits:
            return "No matching documents."
        return "\n".join(hits)

    return search_docs


# ---------------------------------------------------------------------------------------------
# create_ticket — writes platform-owned state (WRITE)
# ---------------------------------------------------------------------------------------------


@tool(
    "create_ticket",
    "Create a support ticket in the platform's tracker. Returns the new ticket id.",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short ticket title."},
            "body": {"type": "string", "description": "Ticket details."},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        },
        "required": ["title"],
    },
    risk=RiskTier.WRITE,
)
def create_ticket(title: str, body: str = "", priority: str = "normal") -> str:
    """Mock ticket creation — in the real platform this calls the ticketing service via ``app/``."""
    if not title or not title.strip():
        raise ToolError("title must be a non-empty string.")
    if priority not in {"low", "normal", "high", "urgent"}:
        raise ToolError("priority must be one of: low, normal, high, urgent.")
    # Deterministic mock id so demos/tests are reproducible; the real tool returns the DB id.
    ticket_id = f"TCK-{abs(hash((title, priority))) % 100000:05d}"
    return f"created ticket {ticket_id} (priority={priority})"


# ---------------------------------------------------------------------------------------------
# send_email — acts on the outside world (EXTERNAL → gated by default)
# ---------------------------------------------------------------------------------------------


@tool(
    "send_email",
    "Send an email to a recipient. Acts on the outside world — requires approval.",
    {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
    risk=RiskTier.EXTERNAL,
)
def send_email(to: str, subject: str, body: str) -> str:
    """Mock email send — gated by the approval policy because it leaves the platform boundary."""
    if "@" not in (to or ""):
        raise ToolError("'to' must be a valid email address.")
    return f"email queued to {to} (subject={subject!r}, {len(body)} chars)"


def default_toolset(retriever: Retriever | None = None) -> ToolRegistry:
    """The registry an agent is handed: read tools, one write tool, one gated external tool.

    Pass ``retriever`` to back ``search_docs`` with the live ``rag/`` pipeline; omit it for the
    offline path. This is the platform's canonical toolset — variants and workers receive it (or a
    confined :meth:`ToolRegistry.subset` of it).
    """
    clock = tool("clock", "Return the current time (ISO-8601, UTC).", risk=RiskTier.READ)(now)
    calculator = tool(
        "calculator",
        "Evaluate an arithmetic expression (+, -, *, /, %, **).",
        {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "e.g. '2 + 3 * 4'"}},
            "required": ["expression"],
        },
        risk=RiskTier.READ,
    )(calculate)
    return ToolRegistry(
        [
            calculator,
            clock,
            make_search_docs(retriever),
            create_ticket,
            send_email,
        ]
    )


# Convenience for callers that just want "a dict of name -> python callable" (e.g. the supervisor's
# scoped worker toolsets), independent of the schema/registry machinery.
def callable_toolset(retriever: Retriever | None = None) -> dict[str, Callable[..., Any]]:
    """The platform tools as plain callables, keyed by name — for lightweight worker wiring."""
    reg = default_toolset(retriever)
    out: dict[str, Callable[..., Any]] = {}
    for name in reg.names():
        t = reg.get(name)
        if t is not None:
            out[name] = t.fn
    return out
