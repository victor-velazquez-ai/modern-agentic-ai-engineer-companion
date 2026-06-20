"""Tools exposed over MCP — pure, schema-declared functions.

A :class:`Tool` is the unit a server exposes and a client calls. It carries:

* a **name** and **description** (what the model sees during discovery),
* an **input schema** (a small JSON-Schema subset, so any MCP client can validate args), and
* a **handler** — a pure Python callable ``(args: dict) -> Any``.

Tools here are deliberately trivial (``add``, ``echo``, ``now``) so the blueprint stays about
*the protocol and the guardrails*, not the business logic. Swap the handlers for real work; the
shapes do not change.

The module also ships :func:`validate_args`, a dependency-free validator for the schema subset.
Both the server (defence in depth) and the safe client (defence at the boundary) use it.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

# A handler takes already-validated arguments and returns a JSON-serialisable result.
Handler = Callable[[Mapping[str, Any]], Any]


class ToolError(Exception):
    """Raised when a tool cannot run (bad args reaching the handler, or a runtime failure).

    The server converts this into a structured error result rather than crashing the
    transport, so one bad call never takes the server down.
    """


# --- JSON-Schema (tiny subset) -------------------------------------------------------------
#
# Supported per-property keys: ``type`` (string|integer|number|boolean|object|array),
# ``enum``, ``minimum``/``maximum`` (numbers), ``minLength``/``maxLength`` (strings).
# Top level supports ``required`` and ``additionalProperties`` (default False — least
# surprise: unknown keys are rejected).

_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "object": (dict,),
    "array": (list,),
}


def validate_args(schema: Mapping[str, Any], args: Mapping[str, Any]) -> dict[str, Any]:
    """Validate ``args`` against a JSON-Schema-subset ``schema``.

    Returns a shallow copy of the validated args on success; raises :class:`ToolError` with a
    human-readable message on the first violation. Pure and side-effect free.
    """
    if not isinstance(args, Mapping):
        raise ToolError(f"arguments must be an object, got {type(args).__name__}")

    props: Mapping[str, Any] = schema.get("properties", {})
    required: list[str] = list(schema.get("required", []))
    additional = schema.get("additionalProperties", False)

    for key in required:
        if key not in args:
            raise ToolError(f"missing required argument: {key!r}")

    if not additional:
        unknown = set(args) - set(props)
        if unknown:
            raise ToolError(f"unexpected argument(s): {', '.join(sorted(unknown))}")

    validated: dict[str, Any] = {}
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:  # only reachable when additionalProperties is True
            validated[key] = value
            continue
        _validate_one(key, value, spec)
        validated[key] = value
    return validated


def _validate_one(key: str, value: Any, spec: Mapping[str, Any]) -> None:
    expected = spec.get("type")
    if expected is not None:
        py_types = _PY_TYPES.get(expected)
        if py_types is None:
            raise ToolError(f"{key!r}: schema declares unknown type {expected!r}")
        # bool is a subclass of int — reject it where a number/integer is wanted.
        if expected in ("integer", "number") and isinstance(value, bool):
            raise ToolError(f"{key!r}: expected {expected}, got boolean")
        if not isinstance(value, py_types):
            raise ToolError(
                f"{key!r}: expected {expected}, got {type(value).__name__}"
            )

    if "enum" in spec and value not in spec["enum"]:
        allowed = ", ".join(repr(v) for v in spec["enum"])
        raise ToolError(f"{key!r}: {value!r} is not one of [{allowed}]")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            raise ToolError(f"{key!r}: {value} < minimum {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            raise ToolError(f"{key!r}: {value} > maximum {spec['maximum']}")

    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            raise ToolError(f"{key!r}: shorter than minLength {spec['minLength']}")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            raise ToolError(f"{key!r}: longer than maxLength {spec['maxLength']}")


@dataclass(frozen=True)
class Tool:
    """A single MCP tool: identity, schema, and a pure handler.

    ``input_schema`` is the JSON-Schema-subset the client uses to validate calls before they
    reach the wire. Keeping the schema *on* the tool is what lets discovery be self-describing.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Handler = field(repr=False)

    def describe(self) -> dict[str, Any]:
        """The discovery payload a client sees from ``tools/list`` (MCP's ``inputSchema``)."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def call(self, args: Mapping[str, Any]) -> Any:
        """Validate ``args`` then run the handler. Raises :class:`ToolError` on either failure."""
        clean = validate_args(self.input_schema, args)
        try:
            return self.handler(clean)
        except ToolError:
            raise
        except Exception as exc:  # a handler bug must not escape as a raw traceback
            raise ToolError(f"tool {self.name!r} failed: {exc}") from exc


# --- Example tools -------------------------------------------------------------------------


def _add(args: Mapping[str, Any]) -> dict[str, Any]:
    return {"sum": args["a"] + args["b"]}


def _echo(args: Mapping[str, Any]) -> dict[str, Any]:
    return {"text": args["text"]}


def _now(args: Mapping[str, Any]) -> dict[str, Any]:
    # Deterministic-friendly: an injectable clock would be wired here in a real system; for the
    # blueprint we read UTC and format to seconds so the shape (not the instant) is the lesson.
    fmt = args.get("format", "iso")
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)
    if fmt == "epoch":
        return {"now": int(now.timestamp())}
    return {"now": now.isoformat()}


def build_default_tools() -> list[Tool]:
    """The example toolset the default server exposes and the demo/tests exercise."""
    return [
        Tool(
            name="add",
            description="Add two numbers and return their sum.",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
            handler=_add,
        ),
        Tool(
            name="echo",
            description="Echo a short string back to the caller.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "maxLength": 280},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=_echo,
        ),
        Tool(
            name="now",
            description="Return the current UTC time as an ISO string or epoch seconds.",
            input_schema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["iso", "epoch"]},
                },
                "required": [],
                "additionalProperties": False,
            },
            handler=_now,
        ),
    ]
