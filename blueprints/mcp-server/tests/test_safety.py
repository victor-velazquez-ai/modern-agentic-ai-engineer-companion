"""Safety: non-allow-listed tools and bad arguments are refused at the boundary."""

from __future__ import annotations

import time

import pytest

from mcp_server.consume import (
    CallTimeout,
    SafeMCPClient,
    ToolNotAllowedError,
    ValidationError,
    as_agent_tools,
)
from mcp_server.server import InProcessTransport, MCPServer, build_default_server
from mcp_server.tools import Tool, ToolError, validate_args


def _ready_client(allow=None, timeout=10.0) -> SafeMCPClient:
    client = SafeMCPClient(
        InProcessTransport(build_default_server()), allow=allow, timeout=timeout
    )
    client.initialize()
    client.discover()
    return client


# --- Guard 1: allow-list / least privilege -------------------------------------------------


def test_default_is_deny_all() -> None:
    client = _ready_client()  # no allow-list
    assert client.allowed == frozenset()
    with pytest.raises(ToolNotAllowedError):
        client.call("add", {"a": 1, "b": 2})


def test_non_allow_listed_tool_is_refused_even_though_discovered() -> None:
    client = _ready_client(allow=["echo"])
    # 'add' is discovered and real, but not allowed → refused before any wire call
    with pytest.raises(ToolNotAllowedError):
        client.call("add", {"a": 1, "b": 2})
    # the allowed one still works
    assert client.call("echo", {"text": "ok"}) == {"text": "ok"}


def test_server_adding_a_dangerous_tool_cannot_reach_an_allow_listed_client() -> None:
    # Simulate a server that *also* exposes a destructive tool. A named allow-list means the
    # new tool is invisible to the agent even after re-discovery.
    server = build_default_server()
    server.add_tool(
        Tool(
            name="delete_all",
            description="DESTRUCTIVE",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=lambda args: {"deleted": "everything"},
        )
    )
    client = SafeMCPClient(InProcessTransport(server), allow=["add"])
    client.initialize()
    client.discover()
    assert "delete_all" in {t.name for t in client.discover()}  # we can SEE it
    with pytest.raises(ToolNotAllowedError):  # but never CALL it
        client.call("delete_all", {})
    assert "delete_all" not in as_agent_tools(client)  # and it's not handed to the agent


# --- Guard 2: argument validation ----------------------------------------------------------


def test_missing_required_argument_refused_locally() -> None:
    client = _ready_client(allow=["add"])
    with pytest.raises(ValidationError):
        client.call("add", {"a": 1})  # missing 'b'


def test_wrong_type_refused() -> None:
    client = _ready_client(allow=["add"])
    with pytest.raises(ValidationError):
        client.call("add", {"a": "not-a-number", "b": 2})


def test_unexpected_argument_refused() -> None:
    client = _ready_client(allow=["echo"])
    with pytest.raises(ValidationError):
        client.call("echo", {"text": "hi", "rogue": True})


def test_enum_and_bounds_enforced() -> None:
    client = _ready_client(allow=["now"])
    with pytest.raises(ValidationError):
        client.call("now", {"format": "nonsense"})  # not in enum


# --- the validator itself (shared by both ends) --------------------------------------------


def test_validator_rejects_bool_as_number() -> None:
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    with pytest.raises(ToolError):
        validate_args(schema, {"x": True})  # bool is not an int here


def test_validator_enforces_string_length() -> None:
    schema = {
        "type": "object",
        "properties": {"s": {"type": "string", "maxLength": 3}},
        "required": ["s"],
        "additionalProperties": False,
    }
    validate_args(schema, {"s": "ok"})  # fine
    with pytest.raises(ToolError):
        validate_args(schema, {"s": "toolong"})


# --- Guard 3: timeout ----------------------------------------------------------------------


def test_slow_server_trips_the_timeout() -> None:
    class SlowServer(MCPServer):
        def handle(self, request):  # noqa: ANN001
            if request.get("method") == "tools/call":
                time.sleep(0.3)
            return super().handle(request)

    server = SlowServer()
    server.add_tool(
        Tool(
            name="echo",
            description="echo",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=lambda args: {"text": args["text"]},
        )
    )
    client = SafeMCPClient(InProcessTransport(server), allow=["echo"], timeout=0.05)
    client.initialize()
    client.discover()
    with pytest.raises(CallTimeout):
        client.call("echo", {"text": "hello"})
