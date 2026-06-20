"""The MCP server: register tools + resources, answer the protocol, own the lifecycle.

This is a faithful-but-small Model Context Protocol server. It speaks a JSON-RPC-2.0-shaped
request/response and implements the methods a client needs to be useful:

==========================  ====================================================
method                      meaning
==========================  ====================================================
``initialize``              handshake; returns server info + capabilities
``tools/list``              discover tools (name, description, inputSchema)
``tools/call``              invoke a tool by name with arguments
``resources/list``          discover read-only resources
``resources/read``          read one resource by uri
``ping``                    liveness
==========================  ====================================================

**Transport is a seam.** The server logic is transport-agnostic: it consumes a request
``dict`` and returns a response ``dict``. :class:`InProcessTransport` wires a client straight to
a server object in the same process — that is the ``MOCK`` / no-network path the demo and tests
use. A production server swaps in a stdio or HTTP+SSE transport behind the same
``send(request) -> response`` method, and nothing above it changes.

The server never raises across the transport boundary: tool/handler failures and unknown
methods come back as JSON-RPC *error* objects, so one bad call can't kill the connection.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .resources import Resource, build_default_resources
from .tools import Tool, ToolError, build_default_tools

PROTOCOL_VERSION = "2024-11-05"  # the MCP revision whose method names we mirror

# JSON-RPC 2.0 error codes (subset) — see the spec.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@runtime_checkable
class Transport(Protocol):
    """A client-facing transport: hand it a request, get a response.

    Implementations differ only in *where* the server lives (same process, a subprocess over
    stdio, a remote HTTP endpoint). The request/response shapes are identical.
    """

    def send(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Send one JSON-RPC request object and return the response object."""
        ...


class MCPServer:
    """An in-memory MCP server you register tools and resources on.

    >>> srv = MCPServer(name="demo")
    >>> _ = [srv.add_tool(t) for t in build_default_tools()]
    >>> srv.handle({"jsonrpc": "2.0", "id": 1, "method": "ping"})["result"]["ok"]
    True
    """

    def __init__(self, name: str = "mcp-server", version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, Tool] = {}
        self._resources: dict[str, Resource] = {}
        self._initialized = False
        self._handlers: dict[str, Callable[[Mapping[str, Any]], Any]] = {
            "initialize": self._on_initialize,
            "ping": self._on_ping,
            "tools/list": self._on_tools_list,
            "tools/call": self._on_tools_call,
            "resources/list": self._on_resources_list,
            "resources/read": self._on_resources_read,
        }

    # --- registration ----------------------------------------------------------------------

    def add_tool(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name!r}")
        self._tools[tool.name] = tool

    def add_resource(self, resource: Resource) -> None:
        if resource.uri in self._resources:
            raise ValueError(f"duplicate resource uri: {resource.uri!r}")
        self._resources[resource.uri] = resource

    # --- request handling ------------------------------------------------------------------

    def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch one JSON-RPC request and always return a well-formed response."""
        req_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or "method" not in request:
            return _error(req_id, INVALID_REQUEST, "not a JSON-RPC 2.0 request")

        method = request["method"]
        handler = self._handlers.get(method)
        if handler is None:
            return _error(req_id, METHOD_NOT_FOUND, f"unknown method: {method!r}")

        # Everything except the handshake/ping requires initialize first (lifecycle).
        if method not in ("initialize", "ping") and not self._initialized:
            return _error(req_id, INVALID_REQUEST, "server not initialized; call 'initialize'")

        params = request.get("params") or {}
        try:
            result = handler(params)
        except ToolError as exc:
            return _error(req_id, INVALID_PARAMS, str(exc))
        except KeyError as exc:
            return _error(req_id, INVALID_PARAMS, f"missing param: {exc}")
        except Exception as exc:  # last-resort guard; never break the transport
            return _error(req_id, INTERNAL_ERROR, f"internal error: {exc}")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # --- method implementations ------------------------------------------------------------

    def _on_initialize(self, params: Mapping[str, Any]) -> dict[str, Any]:
        self._initialized = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": self.name, "version": self.version},
            "capabilities": {"tools": {}, "resources": {}},
        }

    def _on_ping(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def _on_tools_list(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"tools": [t.describe() for t in self._tools.values()]}

    def _on_tools_call(self, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params["name"]
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"no such tool: {name!r}")
        arguments = params.get("arguments", {})
        # Defence in depth: the server validates even though a safe client already did.
        result = tool.call(arguments)
        return {"content": result, "isError": False}

    def _on_resources_list(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"resources": [r.describe() for r in self._resources.values()]}

    def _on_resources_read(self, params: Mapping[str, Any]) -> dict[str, Any]:
        uri = params["uri"]
        resource = self._resources.get(uri)
        if resource is None:
            raise ToolError(f"no such resource: {uri!r}")
        return resource.read()


class InProcessTransport:
    """The ``MOCK``/offline transport: route requests straight to a server in this process.

    No sockets, no subprocess, no keys — the entire MCP round-trip happens via a method call.
    This is what makes the blueprint runnable for free and deterministically in CI.
    """

    def __init__(self, server: MCPServer) -> None:
        self._server = server

    def send(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._server.handle(request)


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def build_default_server(name: str = "demo") -> MCPServer:
    """A server pre-loaded with the example tools and resources."""
    server = MCPServer(name=name)
    for tool in build_default_tools():
        server.add_tool(tool)
    for resource in build_default_resources():
        server.add_resource(resource)
    return server
