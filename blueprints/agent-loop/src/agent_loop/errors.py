"""Failure handling: malformed-call repair and the retry policy (Ch 12/16).

Real models emit broken tool calls: arguments that are a JSON *string* instead of an object, a
trailing comma, ```` ```json ```` fences around the payload, an empty body. A toy loop crashes on
these. A shipped loop **repairs what it safely can**, and for the rest hands the model a precise
error result so it can fix the call itself on the next turn — the cheapest, most robust recovery
there is.

This module is pure (no I/O, no model calls) so the repair rules are unit-testable in isolation.
The loop wires them in; the policy lives here.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .messages import ToolCall

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class MalformedToolCall(ValueError):
    """Raised when a model's tool call can't be coerced into ``{name, arguments-as-object}``.

    The loop catches this and turns it into a model-readable error result rather than crashing —
    the message is written to be actionable ("send arguments as a JSON object"), because the model
    is the thing that reads it and retries.
    """


def repair_arguments(raw: Any) -> dict[str, Any]:
    """Coerce a model's raw ``arguments`` payload into an object, repairing common breakage.

    Handles, in order:

    * already a ``dict`` -> returned as-is;
    * ``None`` or ``""`` -> ``{}`` (a no-arg tool call is legitimate);
    * a JSON *string* -> parsed, stripping ```` ``` ```` fences first;
    * a parsed-but-non-object JSON value (e.g. ``"[1, 2]"`` or ``"42"``) -> rejected, because a
      tool's arguments must be a named mapping.

    Raises :class:`MalformedToolCall` with an actionable message on anything it can't repair.
    """
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = _FENCE.sub("", raw).strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedToolCall(
                f"tool arguments were not valid JSON ({exc.msg}); "
                "send a single JSON object like {\"key\": value}."
            ) from exc
        if not isinstance(parsed, dict):
            raise MalformedToolCall(
                f"tool arguments parsed to {type(parsed).__name__}, but must be a JSON object."
            )
        return parsed
    raise MalformedToolCall(
        f"tool arguments must be an object or a JSON string, got {type(raw).__name__}."
    )


def repair_tool_call(
    *,
    id: str,
    name: Any,
    arguments: Any,
) -> ToolCall:
    """Build a clean :class:`ToolCall` from a model's raw fields, or raise :class:`MalformedToolCall`.

    A missing/blank tool *name* is unrecoverable here (there's nothing to dispatch to), so it
    raises; the loop reports it back to the model. Arguments are run through
    :func:`repair_arguments`.
    """
    if not isinstance(name, str) or not name.strip():
        raise MalformedToolCall("tool call is missing a tool 'name'.")
    return ToolCall(id=str(id) or "call_0", name=name.strip(), arguments=repair_arguments(arguments))


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many *consecutive* failing turns the loop tolerates before giving up.

    A "failing turn" is one where every tool result came back ``ok=False`` (or a call was so
    malformed it couldn't be dispatched). The model is allowed to read the error and retry; this
    bounds how long we let it flail so a stuck model can't burn the whole turn budget on the same
    broken call.

    * ``max_consecutive_tool_failures`` — give up after this many bad turns in a row (the count
      resets the moment a turn makes progress).
    """

    max_consecutive_tool_failures: int = 3

    def exhausted(self, consecutive_failures: int) -> bool:
        return consecutive_failures >= self.max_consecutive_tool_failures
