"""Server side: registration, the initialize handshake, lifecycle, and resources."""

from __future__ import annotations

import pytest

from mcp_server.resources import build_default_resources
from mcp_server.server import (
    METHOD_NOT_FOUND,
    PROTOCOL_VERSION,
    MCPServer,
    build_default_server,
)
from mcp_server.tools import Tool, build_default_tools


def _rpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


def test_registration_lists_tools_and_resources() -> None:
    server = build_default_server()
    server.handle(_rpc("initialize"))

    tools = server.handle(_rpc("tools/list"))["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"add", "echo", "now"} <= names
    # every advertised tool carries an inputSchema (self-describing discovery)
    assert all("inputSchema" in t for t in tools)

    resources = server.handle(_rpc("resources/list"))["result"]["resources"]
    uris = {r["uri"] for r in resources}
    assert "mem://readme" in uris


def test_duplicate_tool_name_rejected() -> None:
    server = MCPServer()
    tool = build_default_tools()[0]
    server.add_tool(tool)
    with pytest.raises(ValueError):
        server.add_tool(tool)


def test_initialize_returns_protocol_and_server_info() -> None:
    server = build_default_server(name="demo")
    result = server.handle(_rpc("initialize"))["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "demo"
    assert "tools" in result["capabilities"]


def test_lifecycle_requires_initialize_first() -> None:
    server = build_default_server()
    # tools/list before initialize is refused...
    blocked = server.handle(_rpc("tools/list"))
    assert "error" in blocked
    # ...but ping is always allowed (liveness)
    assert server.handle(_rpc("ping"))["result"]["ok"] is True
    # after initialize it works
    server.handle(_rpc("initialize"))
    assert "result" in server.handle(_rpc("tools/list"))


def test_unknown_method_is_an_error_not_a_crash() -> None:
    server = build_default_server()
    server.handle(_rpc("initialize"))
    response = server.handle(_rpc("does/not/exist"))
    assert response["error"]["code"] == METHOD_NOT_FOUND


def test_tools_call_runs_the_handler() -> None:
    server = build_default_server()
    server.handle(_rpc("initialize"))
    response = server.handle(
        _rpc("tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}})
    )
    assert response["result"]["content"] == {"sum": 5}
    assert response["result"]["isError"] is False


def test_resource_read_returns_contents() -> None:
    server = build_default_server()
    server.handle(_rpc("initialize"))
    response = server.handle(_rpc("resources/read", {"uri": "mem://readme"}))
    contents = response["result"]["contents"]
    assert contents[0]["uri"] == "mem://readme"
    assert "Demo MCP Server" in contents[0]["text"]


def test_handler_failure_becomes_structured_error() -> None:
    # a tool whose handler raises must surface as a JSON-RPC error, not break the transport
    def _boom(args):  # noqa: ANN001
        raise RuntimeError("kaboom")

    server = MCPServer()
    server.add_tool(
        Tool(
            name="boom",
            description="always fails",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_boom,
        )
    )
    server.handle(_rpc("initialize"))
    response = server.handle(_rpc("tools/call", {"name": "boom", "arguments": {}}))
    assert "error" in response
    assert "kaboom" in response["error"]["message"]


def test_default_resources_are_read_only_shaped() -> None:
    for resource in build_default_resources():
        payload = resource.read()
        assert payload["contents"][0]["uri"] == resource.uri
