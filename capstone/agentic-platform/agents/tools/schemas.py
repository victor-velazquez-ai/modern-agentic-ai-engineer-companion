"""Tool schemas, risk tiers, the safe executor, and dispatch (Ch 12, 20, 41).

A tool has two faces: a **schema** the model reads to decide whether and how to call it (name,
description, JSON-Schema for arguments), and a **function** the loop runs to get a result.
:class:`Tool` binds the two, and adds the one thing the *platform* needs that a toy loop omits —
a declared **risk tier** (Ch 20). The tier is metadata the approval gate reads to decide whether
a call may run unattended or must pause for a human; the tool author declares it once, here, next
to the schema, so risk is a reviewable property of the tool rather than a scattered policy.

:class:`ToolRegistry` is the dispatch table every agent variant shares. It is where the hardening
lives that a toy loop skips: an unknown-tool error becomes a *result the model can read and
recover from* (not a crash); a tool that raises is caught and turned into an error result; a
batch of calls in one assistant turn runs in order with each failure isolated. Validation is
intentionally light (presence/shape of required args) — deeper input policy belongs to the
``llm/gateway.py`` guards and the ``security/`` module; a raw loop should fail *soft* and let the
model try again.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .messages import ToolCall, ToolResult

# A tool implementation takes a decoded argument mapping and returns something stringifiable.
ToolFn = Callable[..., Any]


class RiskTier(str, Enum):
    """How dangerous a tool is to run unattended — the axis the approval gate (Ch 20) reads.

    * ``READ``    — read-only, no side effects (search, lookup). Always auto-approved.
    * ``WRITE``   — mutates internal state the platform owns (create a ticket, write a note).
                    Auto-approved by default; a stricter policy may gate it.
    * ``EXTERNAL``— acts on the outside world or spends money (send an email, call a paid API,
                    place an order). Gated by default — a human approves before it runs.
    * ``ADMIN``   — privileged/irreversible (delete data, change permissions, run shell). Always
                    gated; this is the tier you never let a model fire on its own.

    Ordering matters: tiers are comparable so a policy can say "gate WRITE and above".
    """

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    ADMIN = "admin"

    @property
    def level(self) -> int:
        return _TIER_ORDER[self]

    def __ge__(self, other: "RiskTier") -> bool:  # type: ignore[override]
        if not isinstance(other, RiskTier):
            return NotImplemented
        return self.level >= other.level

    def __gt__(self, other: "RiskTier") -> bool:  # type: ignore[override]
        if not isinstance(other, RiskTier):
            return NotImplemented
        return self.level > other.level

    def __le__(self, other: "RiskTier") -> bool:  # type: ignore[override]
        if not isinstance(other, RiskTier):
            return NotImplemented
        return self.level <= other.level

    def __lt__(self, other: "RiskTier") -> bool:  # type: ignore[override]
        if not isinstance(other, RiskTier):
            return NotImplemented
        return self.level < other.level


_TIER_ORDER: dict[RiskTier, int] = {
    RiskTier.READ: 0,
    RiskTier.WRITE: 1,
    RiskTier.EXTERNAL: 2,
    RiskTier.ADMIN: 3,
}


class ToolError(Exception):
    """Raised inside a tool to signal a clean, model-readable failure.

    Prefer raising this (with a helpful message) over a bare exception: its message is what the
    model sees in the error result, so a good message is a faster recovery. Any *other* exception a
    tool raises is still caught by dispatch and reported — this type just lets you control the
    wording.
    """


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """The model-facing description of a tool (its wire schema).

    ``parameters`` is a JSON-Schema object describing the arguments. The model port renders this
    into whatever the SDK expects; the loop passes specs straight through.
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )

    def required(self) -> list[str]:
        req = self.parameters.get("required", [])
        return list(req) if isinstance(req, list) else []


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable tool: its :class:`ToolSpec`, the function that runs it, and its risk tier."""

    spec: ToolSpec
    fn: ToolFn
    risk: RiskTier = RiskTier.READ

    @property
    def name(self) -> str:
        return self.spec.name


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    *,
    risk: RiskTier = RiskTier.READ,
) -> Callable[[ToolFn], Tool]:
    """Decorator that turns a plain function into a :class:`Tool`.

    >>> @tool("clock", "Return the current time.")
    ... def clock() -> str:
    ...     return "12:00"
    >>> clock.name
    'clock'
    >>> clock.risk.value
    'read'

    Keeping the schema explicit (rather than inferring it from the signature) is deliberate: the
    description is *prompt surface* the model reads, and you want to write it by hand. ``risk``
    defaults to the safest tier; declare a higher one for anything that mutates or spends.
    """

    schema = parameters or {"type": "object", "properties": {}}

    def wrap(fn: ToolFn) -> Tool:
        return Tool(
            spec=ToolSpec(name=name, description=description, parameters=schema),
            fn=fn,
            risk=risk,
        )

    return wrap


class ToolRegistry:
    """The set of tools a loop may call, keyed by name — the dispatch table.

    Construction validates uniqueness (two tools with the same name is a programming error and
    fails fast). Everything else is designed to *not* fail fast: at run time, a bad call from the
    model yields an error :class:`ToolResult`, never an exception, so the loop can hand the model
    its mistake and let it retry.
    """

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._by_name: dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, t: Tool) -> "ToolRegistry":
        if t.name in self._by_name:
            raise ValueError(f"duplicate tool name {t.name!r}")
        self._by_name[t.name] = t
        return self

    def __contains__(self, name: object) -> bool:
        return name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)

    def get(self, name: str) -> Tool | None:
        return self._by_name.get(name)

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def specs(self) -> list[ToolSpec]:
        """The schemas to advertise to the model (stable order for reproducibility)."""
        return [self._by_name[n].spec for n in self.names()]

    def risk_of(self, name: str) -> RiskTier:
        """The declared risk tier of a tool — the approval gate's input. Unknown → ``ADMIN``.

        An unknown tool defaults to the *most* restrictive tier on purpose: a call we can't reason
        about must not be allowed to run unattended.
        """
        t = self._by_name.get(name)
        return t.risk if t is not None else RiskTier.ADMIN

    def subset(self, names: set[str]) -> "ToolRegistry":
        """A registry containing only ``names`` — capability confinement for a worker (Ch 17)."""
        return ToolRegistry([self._by_name[n] for n in self.names() if n in names])

    def execute(self, call: ToolCall) -> ToolResult:
        """Run one tool call, catching *every* failure into an error :class:`ToolResult`.

        The failure ladder, in order: unknown tool → missing required args → tool raised
        (:class:`ToolError` or any other exception). A success path stringifies the return value.
        The point throughout: dispatch *always* returns a ``ToolResult``.
        """
        t = self._by_name.get(call.name)
        if t is None:
            available = ", ".join(self.names()) or "(none)"
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"unknown tool {call.name!r}. Available tools: {available}.",
                ok=False,
            )

        missing = [r for r in t.spec.required() if r not in call.arguments]
        if missing:
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"missing required argument(s): {', '.join(missing)}.",
                ok=False,
            )

        try:
            result = _invoke(t.fn, call.arguments)
        except ToolError as exc:
            return ToolResult(call_id=call.id, name=call.name, content=str(exc), ok=False)
        except Exception as exc:  # a bug in the tool must not kill the loop
            return ToolResult(
                call_id=call.id,
                name=call.name,
                content=f"{type(exc).__name__}: {exc}",
                ok=False,
            )

        return ToolResult(call_id=call.id, name=call.name, content=_stringify(result), ok=True)

    def execute_all(self, calls: list[ToolCall]) -> list[ToolResult]:
        """Execute a batch of calls (one assistant turn may request several), failures isolated.

        Calls run sequentially in emission order, each isolated: one tool's failure does not stop
        the next. (A real system may run independent calls concurrently; deterministic order is
        what a reproducible loop wants by default.)
        """
        return [self.execute(c) for c in calls]


def _invoke(fn: ToolFn, arguments: dict[str, Any]) -> Any:
    """Call ``fn`` with ``arguments``, adapting to its signature.

    A zero-parameter tool is called with no args even if the model sent an empty object; a tool
    that declares ``**kwargs`` gets the whole mapping; otherwise we pass only the keyword
    arguments the function actually accepts. Saves tool authors from ``def f(**kwargs)`` boilerplate
    just to be dispatch-safe.
    """
    sig = inspect.signature(fn)
    params = sig.parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(**arguments)
    accepted = {k: v for k, v in arguments.items() if k in params}
    return fn(**accepted)


def _stringify(value: Any) -> str:
    """Render a tool's return value as the text the model will read."""
    if isinstance(value, str):
        return value
    return repr(value)
