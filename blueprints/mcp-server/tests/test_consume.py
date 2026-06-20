"""Consumption side: a client discovers tools over the transport and invokes one."""

from __future__ import annotations

from mcp_server.consume import SafeMCPClient, as_agent_tools
from mcp_server.server import InProcessTransport, build_default_server


def _client(allow=None) -> SafeMCPClient:
    transport = InProcessTransport(build_default_server())
    client = SafeMCPClient(transport, allow=allow)
    client.initialize()
    client.discover()
    return client


def test_discover_returns_advertised_tools_with_schemas() -> None:
    client = _client()
    discovered = {t.name: t for t in client.discover()}
    assert {"add", "echo", "now"} <= set(discovered)
    assert discovered["add"].input_schema["required"] == ["a", "b"]


def test_allowed_tool_invokes_and_returns_content() -> None:
    client = _client(allow=["add"])
    assert client.call("add", {"a": 4, "b": 5}) == {"sum": 9}


def test_named_grant_after_discovery() -> None:
    client = _client()  # deny-all by default
    client.allow_tool("echo")
    assert client.call("echo", {"text": "hi"}) == {"text": "hi"}


def test_allow_all_discovered_opens_the_in_house_set() -> None:
    client = _client()
    client.allow_all_discovered()
    assert client.is_allowed("now")
    out = client.call("now", {"format": "epoch"})
    assert isinstance(out["now"], int)


def test_as_agent_tools_yields_named_callables_for_allowed_only() -> None:
    # This is the agent-loop composition seam: {name: callable}, guarded.
    client = _client(allow=["add", "echo"])
    toolset = as_agent_tools(client)
    assert set(toolset) == {"add", "echo"}
    # each is a plain callable taking keyword args and routing through the guards
    assert toolset["add"](a=10, b=1) == {"sum": 11}
    assert toolset["echo"].__name__ == "echo"


def test_round_trip_uses_only_the_transport_seam() -> None:
    # The client never touches the server object directly — only transport.send().
    calls: list[str] = []
    inner = InProcessTransport(build_default_server())

    class Spy:
        def send(self, request):  # noqa: ANN001
            calls.append(request["method"])
            return inner.send(request)

    client = SafeMCPClient(Spy(), allow=["add"])
    client.initialize()
    client.discover()
    client.call("add", {"a": 1, "b": 1})
    assert calls == ["initialize", "tools/list", "tools/call"]
