"""Tool dispatch: schema, good calls, bad args, unknown tools, batches, failure isolation."""

from __future__ import annotations

import pytest

from agent_loop import (
    ToolCall,
    ToolError,
    ToolRegistry,
    tool,
)


@tool(
    "divide",
    "Divide a by b.",
    {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    },
)
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ToolError("cannot divide by zero")
    return a / b


@tool("now", "Return a fixed timestamp.")
def now() -> str:
    return "2026-06-20T00:00:00Z"


@tool("boom", "A tool with a bug.")
def boom() -> str:
    raise RuntimeError("kaboom")  # not a ToolError — simulates a real bug


def reg() -> ToolRegistry:
    return ToolRegistry([divide, now, boom])


# --- registry construction -------------------------------------------------------------

def test_duplicate_tool_name_is_rejected():
    with pytest.raises(ValueError):
        ToolRegistry([now, now])


def test_specs_are_advertised_in_stable_order():
    assert reg().names() == ["boom", "divide", "now"]
    specs = reg().specs()
    assert {s.name for s in specs} == {"boom", "divide", "now"}
    # the schema the model reads is carried through verbatim
    div = next(s for s in specs if s.name == "divide")
    assert div.required() == ["a", "b"]


# --- happy path ------------------------------------------------------------------------

def test_execute_good_call_stringifies_result():
    result = reg().execute(ToolCall(id="1", name="divide", arguments={"a": 6, "b": 2}))
    assert result.ok
    assert result.content == "3.0"
    assert result.call_id == "1"


def test_zero_arg_tool_ignores_extra_arguments():
    """A no-param tool called with an empty (or junk) object still runs."""
    result = reg().execute(ToolCall(id="1", name="now", arguments={"unexpected": 1}))
    assert result.ok
    assert result.content == "2026-06-20T00:00:00Z"


# --- bad calls become results, never exceptions ----------------------------------------

def test_unknown_tool_returns_readable_error():
    result = reg().execute(ToolCall(id="1", name="nope", arguments={}))
    assert not result.ok
    assert "unknown tool 'nope'" in result.content
    # the error lists what *is* available, so the model can self-correct
    assert "divide" in result.content


def test_missing_required_argument_is_reported():
    result = reg().execute(ToolCall(id="1", name="divide", arguments={"a": 1}))
    assert not result.ok
    assert "missing required argument" in result.content
    assert "b" in result.content


def test_intentional_tool_error_is_caught():
    result = reg().execute(ToolCall(id="1", name="divide", arguments={"a": 1, "b": 0}))
    assert not result.ok
    assert result.content == "cannot divide by zero"


def test_unexpected_tool_bug_is_caught_not_propagated():
    result = reg().execute(ToolCall(id="1", name="boom", arguments={}))
    assert not result.ok
    assert "RuntimeError" in result.content
    assert "kaboom" in result.content


# --- batch dispatch --------------------------------------------------------------------

def test_execute_all_isolates_failures():
    """One failing call in a batch must not stop the others."""
    calls = [
        ToolCall(id="1", name="divide", arguments={"a": 8, "b": 4}),
        ToolCall(id="2", name="divide", arguments={"a": 1, "b": 0}),  # fails
        ToolCall(id="3", name="now", arguments={}),
    ]
    results = reg().execute_all(calls)
    assert [r.ok for r in results] == [True, False, True]
    assert results[0].content == "2.0"
    assert results[2].content == "2026-06-20T00:00:00Z"


def test_results_correlate_by_call_id():
    calls = [
        ToolCall(id="alpha", name="now", arguments={}),
        ToolCall(id="beta", name="now", arguments={}),
    ]
    results = reg().execute_all(calls)
    assert [r.call_id for r in results] == ["alpha", "beta"]
