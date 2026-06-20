"""Tool registry.

Tools are registered here so the agent loop can (a) advertise their schemas to the
model and (b) dispatch a tool call by name to the right Python function.

To add a tool:
  1. Write it in its own module (see ``example_tool.py``) with a ``TOOL_DEFINITION``
     dict and an implementation function.
  2. Register it below in ``REGISTRY``.

That's the only wiring step — ``tool_definitions()`` and ``run_tool()`` pick it up.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.tools.example_tool import TOOL_DEFINITION as CALCULATE_DEFINITION
from app.tools.example_tool import calculate


def _calculate_handler(tool_input: dict[str, Any]) -> str:
    """Adapt the model's tool_use input dict to the typed ``calculate`` function."""
    return str(calculate(str(tool_input["expression"])))


# name -> (schema, handler). The handler takes the model's input dict and returns a
# string result to feed back as a tool_result.
# ▢ TODO: register your own tools here.
REGISTRY: dict[str, tuple[dict[str, Any], Callable[[dict[str, Any]], str]]] = {
    CALCULATE_DEFINITION["name"]: (CALCULATE_DEFINITION, _calculate_handler),
}


def tool_definitions() -> list[dict[str, Any]]:
    """Return the list of tool schemas to pass to the model API."""
    return [definition for definition, _ in REGISTRY.values()]


def run_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch a tool call by ``name`` and return its string result.

    Raises:
        KeyError: if no tool with that name is registered.
    """
    _, handler = REGISTRY[name]
    return handler(tool_input)
