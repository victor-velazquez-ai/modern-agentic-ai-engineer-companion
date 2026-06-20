"""agent_loop — a framework-free, tool-using agent loop you can read top to bottom.

The hardened version of the toy loop in the Ch 12 walkthrough: the ``observe -> decide -> act ->
observe`` cycle implemented directly against a model port, with the parts a senior would actually
ship — a turn cap, tool-error recovery, malformed-call repair, parallel-call dispatch, and
cancellation — and **no orchestration library hiding the control flow**.

Design goals
------------
* **Free & deterministic standalone.** ``AgentLoop()`` with no arguments uses the offline
  :class:`MockModel` (``COMPANION_MOCK=1``, the default), so the loop — and everything that builds
  on it — runs with zero keys and zero spend, identically every time.
* **Importable, stable surface.** This is the lowest-level pattern; other blueprints and the
  capstone (``agents/raw/``) import it. The model is injected through one seam
  (:class:`ModelPort`), so a real ``llm-gateway`` client drops in without touching the loop.
* **Tooling, not cells.** The turn cap, the dispatch table, malformed-JSON repair, and the
  recovery policy are exactly what ``tests/`` asserts.

Quick start
-----------
>>> from agent_loop import AgentLoop, ToolRegistry, tool, MockModel, assistant, ToolCall
>>> @tool("add", "Add two ints.",
...       {"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
...        "required": ["a", "b"]})
... def add(a: int, b: int) -> int:
...     return a + b
>>> model = MockModel([
...     assistant(tool_calls=(ToolCall(id="1", name="add", arguments={"a": 2, "b": 3}),)),
...     lambda t: assistant(text=f"The answer is {t[-1].text}."),
... ])
>>> loop = AgentLoop(model=model, tools=ToolRegistry([add]))
>>> result = loop.run("what is 2 + 3?")
>>> result.output
'The answer is 5.'
>>> result.ok
True
"""

from __future__ import annotations

from .errors import (
    MalformedToolCall,
    RetryPolicy,
    repair_arguments,
    repair_tool_call,
)
from .loop import (
    AgentLoop,
    AgentResult,
    CancelFn,
    StopReason,
    run_agent,
)
from .messages import (
    Message,
    Role,
    ToolCall,
    ToolResult,
    Transcript,
    assistant,
    system,
    tool as tool_message,
    user,
)
from .model import (
    MockModel,
    ModelPort,
    ModelResponse,
    ScriptStep,
    default_model,
    echo_calculator_clock,
)
from .tools import (
    Tool,
    ToolError,
    ToolFn,
    ToolRegistry,
    ToolSpec,
    tool,
)

__all__ = [
    # loop
    "AgentLoop",
    "AgentResult",
    "StopReason",
    "CancelFn",
    "run_agent",
    # messages / ledger
    "Transcript",
    "Message",
    "Role",
    "ToolCall",
    "ToolResult",
    "system",
    "user",
    "assistant",
    "tool_message",
    # tools
    "Tool",
    "ToolSpec",
    "ToolRegistry",
    "ToolError",
    "ToolFn",
    "tool",
    # model port
    "ModelPort",
    "ModelResponse",
    "MockModel",
    "ScriptStep",
    "default_model",
    "echo_calculator_clock",
    # errors / recovery
    "RetryPolicy",
    "MalformedToolCall",
    "repair_arguments",
    "repair_tool_call",
]

__version__ = "0.1.0"
