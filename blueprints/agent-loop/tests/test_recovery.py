"""Recovery: the model emits a broken tool call, the loop repairs/reports, and it recovers.

These are the tests that justify shipping a *hardened* loop instead of the toy one: a real model
sends malformed JSON, a wrong tool name, an empty body. The loop must turn each into a
model-readable error and keep going — and give up gracefully if the model never stops failing.
"""

from __future__ import annotations

import pytest

from agent_loop import (
    AgentLoop,
    MalformedToolCall,
    MockModel,
    RetryPolicy,
    StopReason,
    ToolCall,
    ToolRegistry,
    assistant,
    repair_arguments,
    repair_tool_call,
    tool,
)


@tool(
    "add",
    "Add two integers.",
    {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    },
)
def add(a: int, b: int) -> int:
    return a + b


def reg() -> ToolRegistry:
    return ToolRegistry([add])


# --- the pure repair rules (unit) ------------------------------------------------------

def test_repair_arguments_passes_dicts_through():
    assert repair_arguments({"a": 1}) == {"a": 1}


def test_repair_arguments_treats_none_and_empty_as_no_args():
    assert repair_arguments(None) == {}
    assert repair_arguments("") == {}
    assert repair_arguments("   ") == {}


def test_repair_arguments_parses_json_string():
    """Models frequently send arguments as a JSON *string* rather than an object."""
    assert repair_arguments('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_repair_arguments_strips_code_fences():
    fenced = '```json\n{"a": 1}\n```'
    assert repair_arguments(fenced) == {"a": 1}


def test_repair_arguments_rejects_unparseable_json():
    with pytest.raises(MalformedToolCall):
        repair_arguments('{"a": 1,}')  # trailing comma, not valid JSON


def test_repair_arguments_rejects_non_object_json():
    with pytest.raises(MalformedToolCall):
        repair_arguments("[1, 2, 3]")


def test_repair_tool_call_requires_a_name():
    with pytest.raises(MalformedToolCall):
        repair_tool_call(id="1", name="", arguments={})


def test_repair_tool_call_repairs_stringified_args():
    call = repair_tool_call(id="1", name="add", arguments='{"a": 4, "b": 5}')
    assert call.arguments == {"a": 4, "b": 5}


# --- the loop recovers (integration) ---------------------------------------------------

def test_loop_recovers_from_a_stringified_arguments_call():
    """First the model sends args as a JSON string (repairable); the loop fixes it and proceeds."""
    model = MockModel(
        [
            # args arrive as a JSON *string* — a toy loop would crash here
            assistant(tool_calls=(ToolCall(id="1", name="add", arguments='{"a": 2, "b": 3}'),)),
            lambda t: assistant(text=f"sum={t[-1].text}"),
        ]
    )
    result = AgentLoop(model=model, tools=reg()).run("add them")

    assert result.ok
    assert result.output == "sum=5"


def test_loop_reports_unknown_tool_then_model_corrects():
    """Model calls a tool that doesn't exist; reads the error; calls the right one; answers."""
    model = MockModel(
        [
            assistant(tool_calls=(ToolCall(id="1", name="sum", arguments={"a": 1, "b": 1}),)),
            # the model "reads" the error result and retries with the correct tool name
            lambda t: assistant(tool_calls=(ToolCall(id="2", name="add", arguments={"a": 1, "b": 1}),)),
            lambda t: assistant(text=f"= {t[-1].text}"),
        ]
    )
    result = AgentLoop(model=model, tools=reg()).run("add 1 and 1")

    assert result.ok
    assert result.output == "= 2"
    # the first (wrong) call produced an error result the model could read
    first_tool_result = next(m for m in result.transcript if m.role == "tool")
    assert not first_tool_result.tool_result.ok
    assert "unknown tool 'sum'" in first_tool_result.text


def test_recovery_exhausted_when_model_keeps_failing():
    """A model that never sends a valid call is stopped by the retry policy, not the turn cap."""
    keep_failing = MockModel(
        [
            assistant(tool_calls=(ToolCall(id=str(i), name="add", arguments={"a": 1}),))  # missing 'b'
            for i in range(10)
        ]
    )
    loop = AgentLoop(
        model=keep_failing,
        tools=reg(),
        max_turns=20,  # generous, so we prove it's recovery (not the cap) that stops us
        retry_policy=RetryPolicy(max_consecutive_tool_failures=3),
    )
    result = loop.run("add")

    assert result.stop_reason is StopReason.RECOVERY_EXHAUSTED
    assert not result.ok
    assert result.turns == 3  # gave up after 3 consecutive failing turns


def test_failure_counter_resets_after_progress():
    """A single failure followed by a good turn must NOT count toward exhaustion."""
    model = MockModel(
        [
            assistant(tool_calls=(ToolCall(id="1", name="add", arguments={"a": 1}),)),   # fail (no b)
            assistant(tool_calls=(ToolCall(id="2", name="add", arguments={"a": 1, "b": 1}),)),  # ok
            lambda t: assistant(text="recovered"),
        ]
    )
    loop = AgentLoop(
        model=model,
        tools=reg(),
        retry_policy=RetryPolicy(max_consecutive_tool_failures=2),
    )
    result = loop.run("add")

    assert result.ok
    assert result.output == "recovered"


def test_malformed_call_is_reported_without_crashing_the_loop():
    """Unrepairable args (bad JSON) become an error result, and the model can still finish."""
    model = MockModel(
        [
            assistant(tool_calls=(ToolCall(id="1", name="add", arguments="not json at all"),)),
            lambda t: assistant(text="ok despite the bad call"),
        ]
    )
    result = AgentLoop(model=model, tools=reg()).run("add")

    assert result.ok
    bad = next(m for m in result.transcript if m.role == "tool")
    assert not bad.tool_result.ok
