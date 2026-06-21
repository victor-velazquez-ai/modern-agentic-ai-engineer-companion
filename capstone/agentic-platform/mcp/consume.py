"""Safe MCP consumption — discover a server's tools and call them behind guards.

The dangerous default is to discover an MCP server's tools and hand them straight
to the model. Don't: a server's tool list can change, its schemas can lie, and an
unfiltered tool is a prompt-injection surface into the agent loop.

:class:`SafeMCPClient` is the boundary that makes consumption safe — four guards,
enforced in code, on every call:

1. **Allow-list (least privilege).** Default deny: only explicitly allowed tool
   names are callable. Discovery still *sees* every tool, but :meth:`call`
   refuses anything off the list — so a server quietly adding ``delete_all`` can
   never reach the model.
2. **Argument validation** against the *discovered* schema, locally, before the
   wire — bad calls fail fast with a clear message and zero round-trips.
3. **Per-call timeout** — a slow or hung server can't stall the agent.
4. **No ambient authority** — the client holds only a transport and its
   allow-list; it grants nothing it wasn't handed.

This is the platform's adaptation of the ``mcp-server`` blueprint's consume side
(same four guards), pointed at the capstone's in-process transport by default.
``as_agent_tools`` exports the allowed set as the ``{name: callable}`` toolset the
agent loop consumes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol, runtime_checkable


@runtime_checkable
class Transport(Protocol):
    """A client-facing transport: hand it a request, get a response."""

    def send(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Send one JSON-RPC request object and return the response object."""
        ...


class SafetyError(Exception):
    """Base class for a refusal by the safe client (a guard fired)."""


class ToolNotAllowedError(SafetyError):
    """The requested tool is not on the allow-list (least privilege)."""


class ValidationError(SafetyError):
    """The call's arguments don't match the tool's discovered schema."""


class RemoteError(SafetyError):
    """The server returned a JSON-RPC error for a call we permitted."""


class CallTimeout(SafetyError):
    """The call exceeded the per-call wall-clock budget."""


# JSON-Schema-subset type checks (the same subset the server's schemas use).
_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> None:
    """Validate ``args`` against a JSON-Schema-subset ``schema``; raise on the first miss."""
    props: Mapping[str, Any] = schema.get("properties", {})
    required: list[str] = list(schema.get("required", []))
    additional = schema.get("additionalProperties", False)

    for key in required:
        if key not in args:
            raise ValidationError(f"missing required argument: {key!r}")

    if not additional:
        unknown = set(args) - set(props)
        if unknown:
            raise ValidationError(f"unexpected argument(s): {', '.join(sorted(unknown))}")

    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            continue
        expected = spec.get("type")
        py_types = _PY_TYPES.get(expected) if expected else None
        if py_types is None:
            continue
        if expected in ("integer", "number") and isinstance(value, bool):
            raise ValidationError(f"{key!r}: expected {expected}, got boolean")
        if not isinstance(value, py_types):
            raise ValidationError(
                f"{key!r}: expected {expected}, got {type(value).__name__}"
            )


@dataclass(frozen=True)
class DiscoveredTool:
    """A tool the client learned about during discovery (its advertised contract)."""

    name: str
    description: str
    input_schema: dict[str, Any]


class SafeMCPClient:
    """A guarded MCP client: discover, then call only what you've allow-listed."""

    def __init__(
        self,
        transport: Transport,
        allow: Iterable[str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._transport = transport
        self._allow: set[str] = set(allow or ())
        self._timeout = float(timeout)
        self._discovered: dict[str, DiscoveredTool] = {}
        self._next_id = 0

    # --- lifecycle / discovery -------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        """Perform the MCP handshake. Required before any other call."""
        return self._request("initialize", {"protocolVersion": "2024-11-05"})

    def discover(self) -> list[DiscoveredTool]:
        """List the server's tools and cache their advertised schemas (observation only)."""
        result = self._request("tools/list", {})
        self._discovered = {
            t["name"]: DiscoveredTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in result.get("tools", [])
        }
        return list(self._discovered.values())

    # --- allow-list management -------------------------------------------------

    def allow_tool(self, name: str) -> None:
        """Add one tool to the allow-list (a deliberate, named grant)."""
        self._allow.add(name)

    def allow_all_discovered(self) -> None:
        """Allow every currently discovered tool (use only for in-house servers)."""
        self._allow.update(self._discovered)

    @property
    def allowed(self) -> frozenset[str]:
        return frozenset(self._allow)

    def is_allowed(self, name: str) -> bool:
        return name in self._allow

    # --- the guarded call ------------------------------------------------------

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        """Invoke a tool through all four guards; raise a :class:`SafetyError` if any refuses."""
        arguments = dict(arguments or {})

        # Guard 1 — allow-list (deny unless explicitly permitted).
        if name not in self._allow:
            raise ToolNotAllowedError(
                f"tool {name!r} is not on the allow-list "
                f"(allowed: {sorted(self._allow) or 'none'})"
            )

        # Guard 2 — validate against the discovered schema, locally, before the wire.
        known = self._discovered.get(name)
        if known is None:
            raise ToolNotAllowedError(
                f"tool {name!r} was not discovered; run discover() first"
            )
        validate_args(known.input_schema, arguments)

        # Guard 3 — per-call timeout.
        response = self._request_with_timeout(
            "tools/call", {"name": name, "arguments": arguments}
        )
        return response.get("content")

    def as_agent_tool(self, name: str) -> Callable[..., Any]:
        """Wrap one allowed tool as a plain ``(**kwargs) -> result`` callable."""

        def _invoke(**kwargs: Any) -> Any:
            return self.call(name, kwargs)

        _invoke.__name__ = name
        known = self._discovered.get(name)
        _invoke.__doc__ = known.description if known else f"MCP tool {name!r}"
        return _invoke

    # --- internals -------------------------------------------------------------

    def _request(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        response = self._transport.send(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": dict(params)}
        )
        if "error" in response:
            err = response["error"]
            raise RemoteError(f"server error {err.get('code')}: {err.get('message')}")
        return response.get("result", {})

    def _request_with_timeout(
        self, method: str, params: Mapping[str, Any]
    ) -> dict[str, Any]:
        box: dict[str, Any] = {}
        error: list[BaseException] = []

        def _run() -> None:
            try:
                box["result"] = self._request(method, params)
            except BaseException as exc:  # re-raised on the caller thread
                error.append(exc)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(self._timeout)
        if worker.is_alive():
            raise CallTimeout(f"call to {method!r} exceeded {self._timeout:g}s budget")
        if error:
            raise error[0]
        return box["result"]


def as_agent_tools(client: SafeMCPClient) -> dict[str, Callable[..., Any]]:
    """Expose every *allowed* discovered tool as a named callable for the agent loop."""
    return {
        name: client.as_agent_tool(name)
        for name in client.allowed
        if name in client._discovered  # only tools actually discovered are callable
    }
