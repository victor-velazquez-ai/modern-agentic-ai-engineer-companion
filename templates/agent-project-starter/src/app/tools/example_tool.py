"""A single, safe example tool: a calculator.

This is the *shape* of a tool — a typed function plus a JSON-Schema definition the
model sees. It does no I/O and has no side effects, so it's safe to wire into the
loop as-is. Replace it (or add alongside it) with your own tools.

A tool here is two things kept in sync:
  1. ``TOOL_DEFINITION`` — the schema the model reads to decide when/how to call it.
  2. ``calculate(...)`` — the Python that actually runs when the model calls it.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

# The schema the model sees. ``name`` must match the key in the registry (see
# tools/__init__.py) so the agent loop can dispatch a tool_use block to the function.
TOOL_DEFINITION: dict[str, Any] = {
    "name": "calculate",
    "description": (
        "Evaluate a basic arithmetic expression and return the numeric result. "
        "Supports + - * / // % ** and parentheses over numbers. "
        "Use this when the user asks for a calculation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "An arithmetic expression, e.g. '21 + 21' or '(3 + 4) * 2'.",
            }
        },
        "required": ["expression"],
    },
}

# Only these operators are allowed — no names, calls, attributes, or comprehensions.
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> float:
    """Safely evaluate an arithmetic ``expression`` and return the result.

    Uses an AST walk over a whitelist of operators instead of ``eval`` — so a
    malicious string can't run arbitrary code.

    Raises:
        ValueError: if the expression contains anything outside the whitelist.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {expression!r}") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Only numbers and + - * / // % ** with parentheses are allowed.")
