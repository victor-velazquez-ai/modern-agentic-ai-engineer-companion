"""Safe MCP consumption — discover a server's tools and call them *behind guardrails*.

The dangerous default in agentic systems is to discover a remote MCP server's tools and hand
them straight to the model. Don't. A remote server is third-party code you don't control; its
tool list can change, its schemas can lie, and a single unfiltered tool is an injection surface.

:class:`SafeMCPClient` is the boundary that makes consumption safe. Four guards, all enforced in
code (not documentation):

1. **Allow-list (least privilege).** Only explicitly allowed tool names are callable. Default
   is *deny*: an empty allow-list exposes nothing. Discovery still *sees* every tool, but
   :meth:`call` refuses anything off the list — so a server quietly adding a ``delete_all`` tool
   can never reach the model.
2. **Argument validation.** Every call is validated against the *discovered* input schema before
   it touches the wire, using the same validator the server trusts. Malformed calls fail fast,
   locally, with a clear message.
3. **Timeout.** Each call runs under a wall-clock budget; a slow or hung server can't stall the
   agent. (In-process calls are instant, but the budget is enforced uniformly.)
4. **Least privilege everywhere.** No ambient capability — the client holds only a transport and
   its allow-list; it grants nothing it wasn't handed.

The client speaks to any :class:`~mcp_server.server.Transport` (in-process for the demo/tests;
stdio/HTTP in production), so the safety layer is independent of how you reach the server.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .server import Transport
from .tools import ToolError, validate_args


class SafetyError(Exception):
    """Base class for a refusal by the safe client (the guard fired)."""


class ToolNotAllowedError(SafetyError):
    """The requested tool is not on the allow-list (least privilege)."""


class ValidationError(SafetyError):
    """The call's arguments don't match the tool's discovered schema."""


class RemoteError(SafetyError):
    """The server returned a JSON-RPC error for a call we permitted."""


class CallTimeout(SafetyError):
    """The call exceeded the per-call wall-clock budget."""


@dataclass(frozen=True)
class DiscoveredTool:
    """A tool the client learned about during discovery (its advertised contract)."""

    name: str
    description: str
    input_schema: dict[str, Any]


class SafeMCPClient:
    """A guarded MCP client: discover, then call only what you've allow-listed.

    Parameters
    ----------
    transport:
        Any object with ``send(request) -> response`` (see
        :class:`~mcp_server.server.Transport`).
    allow: optional iterable of tool names
        The allow-list. Default *deny-all* (empty). Pass the names you trust, or call
        :meth:`allow_tool` / :meth:`allow_all_discovered` after discovery.
    timeout: float
        Per-call wall-clock budget in seconds.
    """

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

    # --- lifecycle / discovery -------------------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        """Perform the MCP handshake. Required before any other call."""
        return self._request("initialize", {"protocolVersion": "2024-11-05"})

    def discover(self) -> list[DiscoveredTool]:
        """List the server's tools and cache their advertised schemas.

        Discovery is *observation only* — it does not grant access. A discovered tool is
        callable only if it is also on the allow-list.
        """
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

    # --- allow-list management -------------------------------------------------------------

    def allow_tool(self, name: str) -> None:
        """Add one tool to the allow-list (a deliberate, named grant)."""
        self._allow.add(name)

    def allow_all_discovered(self) -> None:
        """Allow every *currently discovered* tool.

        A convenience for trusted, in-house servers. Use named grants for third-party ones —
        this opens whatever the server advertised at discovery time.
        """
        self._allow.update(self._discovered)

    @property
    def allowed(self) -> frozenset[str]:
        return frozenset(self._allow)

    def is_allowed(self, name: str) -> bool:
        return name in self._allow

    # --- the guarded call ------------------------------------------------------------------

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        """Invoke a tool through all four guards. Raises a :class:`SafetyError` subclass if any
        guard refuses; returns the tool's ``content`` on success."""
        arguments = dict(arguments or {})

        # Guard 1 — allow-list (least privilege; deny unless explicitly permitted).
        if name not in self._allow:
            raise ToolNotAllowedError(
                f"tool {name!r} is not on the allow-list "
                f"(allowed: {sorted(self._allow) or 'none'})"
            )

        # Guard 2 — validate against the *discovered* schema, locally, before the wire.
        known = self._discovered.get(name)
        if known is None:
            raise ToolNotAllowedError(
                f"tool {name!r} was not discovered; run discover() first"
            )
        try:
            validate_args(known.input_schema, arguments)
        except ToolError as exc:
            raise ValidationError(f"invalid arguments for {name!r}: {exc}") from exc

        # Guard 3 — per-call timeout.
        response = self._request_with_timeout(
            "tools/call", {"name": name, "arguments": arguments}
        )
        return response.get("content")

    def as_agent_tool(self, name: str) -> Callable[..., Any]:
        """Return a plain callable wrapping :meth:`call` for one allowed tool.

        This is the seam to ``agent-loop``: an agent's toolset is a set of named callables, and
        each MCP tool becomes one — already guarded. See :func:`as_agent_tools`.
        """

        def _invoke(**kwargs: Any) -> Any:
            return self.call(name, kwargs)

        _invoke.__name__ = name
        known = self._discovered.get(name)
        _invoke.__doc__ = known.description if known else f"MCP tool {name!r}"
        return _invoke

    # --- internals -------------------------------------------------------------------------

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
        # A transport-agnostic wall-clock budget: run the request on a worker thread and join
        # with the timeout. (For a real stdio/HTTP transport you'd also cancel the underlying
        # I/O; in-process work is uninterruptible, so we surface the timeout and move on.)
        box: dict[str, Any] = {}
        error: list[BaseException] = []

        def _run() -> None:
            try:
                box["result"] = self._request(method, params)
            except BaseException as exc:  # noqa: BLE001 — re-raised on the caller thread
                error.append(exc)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(self._timeout)
        if worker.is_alive():
            raise CallTimeout(
                f"call to {method!r} exceeded {self._timeout:g}s budget"
            )
        if error:
            raise error[0]
        return box["result"]


def as_agent_tools(client: SafeMCPClient) -> dict[str, Callable[..., Any]]:
    """Expose every *allowed* discovered tool as a named callable.

    The return value is exactly the toolset shape ``agent-loop`` consumes: ``{name: callable}``.
    An agent driving these reaches the MCP server only through the guards above — discovery,
    allow-list, validation, and timeout are already applied. This is the composition point the
    PLAN calls out: *the consumption side feeds discovered MCP tools into a loop's toolset.*
    """
    return {
        name: client.as_agent_tool(name)
        for name in client.allowed
        if name in client._discovered  # only tools we actually discovered are callable
    }
