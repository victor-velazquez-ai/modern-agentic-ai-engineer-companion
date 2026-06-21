"""A tiny in-process MCP server that mimics the ``FastMCP`` decorator API.

This is the ``MOCK`` / offline path :func:`mcp.server.build_server` falls back to
when the real ``mcp`` package is not installed (or ``COMPANION_MOCK`` is set). It
exposes the same registration surface ``FastMCP`` does — ``.tool()``,
``.resource()`` and ``.prompt()`` decorators — and derives each tool's JSON
schema from the function's type hints and docstring, exactly as ``FastMCP`` does.
That lets ``mcp/server.py`` register tools once against either object.

It also answers the MCP request methods a client speaks (``initialize``,
``tools/list``, ``tools/call``, ``resources/list``, ``resources/read``,
``prompts/list``, ``prompts/get``, ``ping``) so the whole round-trip runs in one
process, with no sockets and no keys. A failing handler comes back as a
structured error, never as a crash across the transport boundary.

This is deliberately the *blueprint's* server shape (see
``blueprints/mcp-server/``) adapted to the FastMCP decorator ergonomics, so the
capstone and the blueprint teach the same mental model.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping

PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 2.0 error codes (subset).
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Python annotation -> JSON-Schema type, the same mapping FastMCP applies.
_JSON_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


class MCPError(Exception):
    """A tool/resource/prompt failure surfaced as a structured protocol error."""


@dataclass(frozen=True)
class _Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass(frozen=True)
class _Resource:
    uri_template: str
    name: str
    description: str
    fn: Callable[..., str]


@dataclass(frozen=True)
class _Prompt:
    name: str
    description: str
    fn: Callable[..., str]


def _build_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Derive a JSON-Schema-subset input schema from a function's signature.

    Mirrors FastMCP: each parameter becomes a property typed from its annotation;
    parameters without a default are ``required``.
    """
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname in {"self", "cls"}:
            continue
        annotation = param.annotation
        json_type = _JSON_TYPES.get(annotation, "string")
        properties[pname] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _first_line(doc: str | None) -> str:
    if not doc:
        return ""
    return inspect.cleandoc(doc).splitlines()[0].strip()


def _uri_pattern(template: str) -> re.Pattern[str]:
    """Turn ``runbook://{name}`` into a regex capturing ``name``."""
    parts = re.split(r"\{(\w+)\}", template)
    out = ["^"]
    for i, part in enumerate(parts):
        out.append(f"(?P<{part}>[^/]+)" if i % 2 else re.escape(part))
    out.append("$")
    return re.compile("".join(out))


class MockMCPServer:
    """In-process MCP server with a FastMCP-compatible decorator API."""

    def __init__(self, name: str = "mock-mcp", version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, _Tool] = {}
        self._resources: list[_Resource] = []
        self._prompts: dict[str, _Prompt] = {}
        self._initialized = False

    # --- registration (FastMCP-shaped decorators) -----------------------------

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[fn.__name__] = _Tool(
                name=fn.__name__,
                description=_first_line(fn.__doc__),
                input_schema=_build_schema(fn),
                fn=fn,
            )
            return fn

        return decorator

    def resource(self, uri_template: str) -> Callable[[Callable[..., str]], Callable[..., str]]:
        def decorator(fn: Callable[..., str]) -> Callable[..., str]:
            self._resources.append(
                _Resource(
                    uri_template=uri_template,
                    name=fn.__name__,
                    description=_first_line(fn.__doc__),
                    fn=fn,
                )
            )
            return fn

        return decorator

    def prompt(self) -> Callable[[Callable[..., str]], Callable[..., str]]:
        def decorator(fn: Callable[..., str]) -> Callable[..., str]:
            self._prompts[fn.__name__] = _Prompt(
                name=fn.__name__,
                description=_first_line(fn.__doc__),
                fn=fn,
            )
            return fn

        return decorator

    # --- direct invocation (handy in tests, no JSON-RPC envelope) --------------

    def call_tool(self, name: str, arguments: Mapping[str, Any] | None = None) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise MCPError(f"no such tool: {name!r}")
        try:
            return tool.fn(**dict(arguments or {}))
        except MCPError:
            raise
        except Exception as exc:  # a handler bug must not escape raw
            raise MCPError(f"tool {name!r} failed: {exc}") from exc

    def read_resource(self, uri: str) -> str:
        for res in self._resources:
            match = _uri_pattern(res.uri_template).match(uri)
            if match:
                return res.fn(**match.groupdict())
        raise MCPError(f"no resource matches uri: {uri!r}")

    def get_prompt(self, name: str, arguments: Mapping[str, Any] | None = None) -> str:
        prompt = self._prompts.get(name)
        if prompt is None:
            raise MCPError(f"no such prompt: {name!r}")
        return prompt.fn(**dict(arguments or {}))

    # --- JSON-RPC-shaped request handling -------------------------------------

    def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch one JSON-RPC request; always return a well-formed response."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        try:
            result = self._dispatch(str(method), params)
        except _NoMethod:
            return _error(req_id, METHOD_NOT_FOUND, f"unknown method: {method!r}")
        except MCPError as exc:
            return _error(req_id, INVALID_PARAMS, str(exc))
        except KeyError as exc:
            return _error(req_id, INVALID_PARAMS, f"missing param: {exc}")
        except Exception as exc:  # last-resort guard; never break the transport
            return _error(req_id, INTERNAL_ERROR, f"internal error: {exc}")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _dispatch(self, method: str, params: Mapping[str, Any]) -> Any:
        if method == "initialize":
            self._initialized = True
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": self.name, "version": self.version},
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            }
        if method == "ping":
            return {"ok": True}
        if method == "tools/list":
            return {"tools": [t.describe() for t in self._tools.values()]}
        if method == "tools/call":
            content = self.call_tool(params["name"], params.get("arguments", {}))
            return {"content": [{"type": "text", "text": str(content)}], "isError": False}
        if method == "resources/list":
            return {
                "resources": [
                    {"uri": r.uri_template, "name": r.name, "description": r.description}
                    for r in self._resources
                ]
            }
        if method == "resources/read":
            text = self.read_resource(params["uri"])
            return {"contents": [{"uri": params["uri"], "text": text}]}
        if method == "prompts/list":
            return {
                "prompts": [
                    {"name": p.name, "description": p.description}
                    for p in self._prompts.values()
                ]
            }
        if method == "prompts/get":
            text = self.get_prompt(params["name"], params.get("arguments", {}))
            return {
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": text}}
                ]
            }
        raise _NoMethod(method)


class _NoMethod(Exception):
    """Internal sentinel: the requested method is not implemented."""


def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


class InProcessTransport:
    """Route requests straight to a :class:`MockMCPServer` in this process.

    The ``send(request) -> response`` seam :mod:`mcp.consume` talks to. A real
    deployment swaps in a stdio or Streamable-HTTP transport behind the same
    method; the safe-consumption guards above it are unchanged.
    """

    def __init__(self, server: MockMCPServer) -> None:
        self._server = server

    def send(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return self._server.handle(request)
