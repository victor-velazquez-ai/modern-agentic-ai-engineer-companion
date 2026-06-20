"""Tools: the schema the model sees, the safe executor, and dispatch (Ch 12).

A tool has two faces:

* **a schema** the model reads to decide *whether and how* to call it (name, description, a
  JSON-Schema for its arguments), and
* **a function** the loop runs to *get a result*.

:class:`Tool` binds the two. :class:`ToolRegistry` is the lookup the loop dispatches through,
and it is where the hardening lives that a toy loop skips: an unknown-tool error becomes a
*result the model can read and recover from* (not a crash); a tool that raises is caught and
turned into an error result; and a batch of calls in one assistant turn is executed in order
with each failure isolated.

Validation is intentionally light here (presence/shape of required args) — the loop's job is to
keep running, not to be a schema validator. The ``llm-gateway`` guards (Ch 41) and the
eval-harness are where deeper input policy belongs; a raw loop should fail *soft* and let the
model try again.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .messages import ToolCall, ToolResult

# A tool implementation takes a decoded argument mapping and returns something stringifiable.
ToolFn = Callable[..., Any]


class ToolError(Exception):
    """Raised inside a tool to signal a clean, model-readable failure.

    Prefer raising this (with a helpful message) over a bare exception: its message is what the
    model sees in the error result, so a good message is a faster recovery. Any *other* exception
    a tool raises is still caught by dispatch and reported — this type just lets you control the
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
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})

    def required(self) -> list[str]:
        req = self.parameters.get("required", [])
        return list(req) if isinstance(req, list) else []


@dataclass(frozen=True, slots=True)
class Tool:
    """A callable tool: its :class:`ToolSpec` plus the function that runs it."""

    spec: ToolSpec
    fn: ToolFn

    @property
    def name(self) -> str:
        return self.spec.name


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
) -> Callable[[ToolFn], Tool]:
    """Decorator that turns a plain function into a :class:`Tool`.

    >>> @tool("clock", "Return the current time.")
    ... def clock() -> str:
    ...     return "12:00"
    >>> clock.name
    'clock'

    Keeping the schema explicit (rather than inferring it from the signature) is deliberate: the
    description is *prompt surface* the model reads, and you want to write it by hand.
    """

    schema = parameters or {"type": "object", "properties": {}}

    def wrap(fn: ToolFn) -> Tool:
        return Tool(spec=ToolSpec(name=name, description=description, parameters=schema), fn=fn)

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

    def names(self) -> list[str]:
        return sorted(self._by_name)

    def specs(self) -> list[ToolSpec]:
        """The schemas to advertise to the model (stable order for reproducibility)."""
        return [self._by_name[n].spec for n in self.names()]

    def execute(self, call: ToolCall) -> ToolResult:
        """Run one tool call, catching *every* failure into an error :class:`ToolResult`.

        The failure ladder, in order:

        1. **Unknown tool** — the model named a tool that isn't registered.
        2. **Missing required args** — a shallow check against the spec's ``required`` list.
        3. **Tool raised** — :class:`ToolError` (intentional) or any other exception (a bug in the
           tool); both become a readable error result rather than propagating.

        A success path stringifies the return value (tools return rich objects; the model reads
        text). The point throughout: dispatch *always* returns a ``ToolResult``.
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
        """Execute a batch of calls (one assistant turn may request several).

        Calls run sequentially in the order the model emitted them, and each is isolated: one
        tool's failure does not stop the next. (A real system may run independent calls
        concurrently — see the README on parallel tool calls — but deterministic order is what a
        reproducible loop wants by default.)
        """
        return [self.execute(c) for c in calls]


def _invoke(fn: ToolFn, arguments: dict[str, Any]) -> Any:
    """Call ``fn`` with ``arguments``, adapting to its signature.

    A zero-parameter tool (``clock``) is called with no args even if the model sent an empty
    object; a tool that declares ``**kwargs`` gets the whole mapping; otherwise we pass only the
    keyword arguments the function actually accepts. This keeps tool authors from having to write
    ``def f(**kwargs)`` boilerplate just to be dispatch-safe.
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
