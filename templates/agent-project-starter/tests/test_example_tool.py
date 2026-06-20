"""The example tool's contract: schema shape, correct math, safe on bad input."""

from __future__ import annotations

import pytest

from app.tools import run_tool, tool_definitions
from app.tools.example_tool import TOOL_DEFINITION, calculate


def test_definition_shape() -> None:
    assert TOOL_DEFINITION["name"] == "calculate"
    schema = TOOL_DEFINITION["input_schema"]
    assert schema["type"] == "object"
    assert "expression" in schema["properties"]
    assert schema["required"] == ["expression"]


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("21 + 21", 42.0),
        ("(3 + 4) * 2", 14.0),
        ("10 / 4", 2.5),
        ("2 ** 5", 32.0),
        ("-7 + 10", 3.0),
        ("17 % 5", 2.0),
    ],
)
def test_calculate_evaluates_arithmetic(expression: str, expected: float) -> None:
    assert calculate(expression) == expected


@pytest.mark.parametrize("expression", ["__import__('os')", "open('x')", "a + b", "1 +"])
def test_calculate_rejects_unsafe_or_invalid(expression: str) -> None:
    with pytest.raises(ValueError):
        calculate(expression)


def test_registry_dispatch() -> None:
    # The tool is registered and dispatchable by name through the registry.
    assert any(d["name"] == "calculate" for d in tool_definitions())
    assert run_tool("calculate", {"expression": "21 + 21"}) == "42.0"
