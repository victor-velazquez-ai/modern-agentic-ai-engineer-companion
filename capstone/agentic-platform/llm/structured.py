"""Structured output — ``complete_structured`` (Ch 15), the model choke point.

When the platform needs *data* from a model (a classification, an extraction, a
tool argument set) rather than prose, it never parses free text by eyeball. It
goes through one function, :func:`complete_structured`, which:

1. **Asks for JSON that matches a schema** — the prompt is augmented with the
   target JSON Schema and an instruction to emit *only* JSON. (On a real provider
   you'd prefer the SDK's constrained-decoding / tool-use path; the shape here is
   provider-agnostic so the mock and any provider behave the same.)
2. **Extracts and parses** the JSON from the response (tolerant of a leading
   ```` ```json ```` fence or surrounding prose).
3. **Validates** against the schema (a Pydantic model if one is given, else a
   minimal built-in JSON-Schema check).
4. **Repairs on failure** — if parsing or validation fails, it feeds the error
   back to the model and retries up to ``max_repairs`` times (the "validate-and-
   retry repair" loop). If it still fails, it raises
   :class:`~core.errors.ValidationError` rather than returning junk.

This is the single seam every "give me typed data" call passes through, so the
parse/validate/repair policy is consistent and testable. It is built on the base
:class:`~llm.client.LLMClient` (and works just as well behind the
:class:`~llm.gateway.Gateway`); structured output *sits on top of* the model door,
it is not a second door.

Mock-runnable: with ``COMPANION_MOCK=1`` the default client returns canned JSON,
so the parse/validate path exercises end to end with no API spend. Tests can pass
an explicit client whose mock is seeded with the JSON to return.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Type, TypeVar, Union

from core.errors import ValidationError

from .client import ChatRequest, LLMClient, Message

# Optional Pydantic — used when a schema is a BaseModel subclass. Imported
# defensively so this module loads (and the dict-schema path runs) without it.
try:  # pragma: no cover - import-environment dependent
    from pydantic import BaseModel
    from pydantic import ValidationError as _PydanticValidationError

    _HAVE_PYDANTIC = True
except Exception:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment,misc]
    _PydanticValidationError = Exception  # type: ignore[assignment,misc]
    _HAVE_PYDANTIC = False

T = TypeVar("T")

# A "schema" is either a Pydantic model class or a plain JSON-Schema dict.
Schema = Union[Type[Any], dict[str, Any]]

_DEFAULT_STRUCTURED_MODEL = "claude-sonnet-4-6"

# Pull the first JSON object/array out of a response that may be fenced or chatty.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_SPAN_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


@dataclass(frozen=True)
class StructuredResult:
    """The validated value plus the trace of how it was obtained.

    ``value`` is what callers want (a Pydantic instance or a dict). ``raw`` is the
    final model text, ``attempts`` counts model calls (1 + repairs), and ``repaired``
    flags that at least one repair round was needed — useful in evals/observability.
    """

    value: Any
    raw: str
    attempts: int
    repaired: bool


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _is_pydantic_model(schema: Schema) -> bool:
    return _HAVE_PYDANTIC and isinstance(schema, type) and issubclass(schema, BaseModel)


def json_schema_of(schema: Schema) -> dict[str, Any]:
    """Return the JSON Schema for either a Pydantic model or a raw dict schema."""

    if _is_pydantic_model(schema):
        return schema.model_json_schema()  # type: ignore[union-attr]
    if isinstance(schema, dict):
        return schema
    raise ValidationError(
        f"schema must be a Pydantic model or a JSON-Schema dict, got {type(schema)!r}"
    )


def _schema_name(schema: Schema) -> str:
    if _is_pydantic_model(schema):
        return schema.__name__  # type: ignore[union-attr]
    if isinstance(schema, dict):
        return str(schema.get("title", "object"))
    return "object"


# ---------------------------------------------------------------------------
# Parsing + validation
# ---------------------------------------------------------------------------


def extract_json(text: str) -> Any:
    """Pull a JSON value out of model text. Tolerant of fences and prose.

    Tries, in order: a ```` ```json ```` fenced block, then the whole string, then
    the first ``{...}``/``[...]`` span. Raises :class:`ValueError` if none parse.
    """

    candidates: list[str] = []
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    candidates.append(text.strip())
    span = _JSON_SPAN_RE.search(text)
    if span:
        candidates.append(span.group(1))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    raise ValueError("no parseable JSON found in model output")


def _validate_jsonschema(data: Any, schema: dict[str, Any]) -> Any:
    """Minimal JSON-Schema validation: type, required, property types.

    A deliberately small stand-in for a full validator (no ``jsonschema`` dep). It
    covers the cases the structured path actually needs — object shape and the
    declared required fields — and raises :class:`ValidationError` on a mismatch.
    For full-spec validation, swap this for ``jsonschema.validate`` at this seam.
    """

    expected = schema.get("type")
    _JSON_TYPES: dict[str, type | tuple[type, ...]] = {
        "object": dict,
        "array": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    if expected in _JSON_TYPES and not isinstance(data, _JSON_TYPES[expected]):
        # bool is a subclass of int — reject it where an integer/number is wanted.
        if not (expected in ("integer", "number") and isinstance(data, bool)):
            raise ValidationError(f"expected JSON {expected}, got {type(data).__name__}")

    if expected == "object" and isinstance(data, dict):
        for field_name in schema.get("required", []):
            if field_name not in data:
                raise ValidationError(f"missing required field: {field_name!r}")
        props: dict[str, Any] = schema.get("properties", {})
        for key, subschema in props.items():
            if key in data and isinstance(subschema, dict) and "type" in subschema:
                sub_t = subschema["type"]
                if sub_t in _JSON_TYPES and not isinstance(data[key], _JSON_TYPES[sub_t]):
                    if not (sub_t in ("integer", "number") and isinstance(data[key], bool)):
                        raise ValidationError(
                            f"field {key!r}: expected {sub_t}, "
                            f"got {type(data[key]).__name__}"
                        )
    return data


def validate(data: Any, schema: Schema) -> Any:
    """Validate parsed ``data`` against ``schema``; return the coerced value.

    For a Pydantic model this returns a validated *instance*; for a dict schema it
    returns the (checked) dict. Raises :class:`ValidationError` on any mismatch.
    """

    if _is_pydantic_model(schema):
        try:
            return schema.model_validate(data)  # type: ignore[union-attr]
        except _PydanticValidationError as exc:
            raise ValidationError(f"schema validation failed: {exc}") from exc
    return _validate_jsonschema(data, json_schema_of(schema))


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _instruction(schema: Schema) -> str:
    pretty = json.dumps(json_schema_of(schema), indent=2)
    return (
        "Respond with a single JSON value that conforms to this JSON Schema. "
        "Output JSON only — no prose, no markdown fences.\n\n"
        f"JSON Schema ({_schema_name(schema)}):\n{pretty}"
    )


def _repair_instruction(bad_text: str, error: str) -> str:
    return (
        "Your previous response did not satisfy the schema.\n"
        f"Error: {error}\n"
        f"Previous output:\n{bad_text}\n\n"
        "Return corrected JSON only — no prose, no fences."
    )


# ---------------------------------------------------------------------------
# The public function
# ---------------------------------------------------------------------------


def complete_structured(
    prompt: str,
    schema: Schema,
    *,
    client: LLMClient | None = None,
    model: str | None = None,
    system: str | None = None,
    max_tokens: int = 1024,
    effort: str | None = None,
    max_repairs: int = 2,
) -> StructuredResult:
    """Get schema-valid data from a model: ask → parse → validate → repair.

    Parameters
    ----------
    prompt:
        The user's request (what data you want).
    schema:
        A Pydantic ``BaseModel`` subclass *or* a JSON-Schema dict. The return
        ``value`` is a validated model instance or a checked dict, respectively.
    client:
        The model door. Defaults to a fresh :class:`~llm.client.LLMClient` (mock
        provider unless ``COMPANION_MOCK=0``). Pass one in tests to seed canned
        JSON, or to route through a shared client.
    max_repairs:
        How many times to feed a validation error back and retry. ``0`` means one
        attempt and no repair.

    Returns
    -------
    StructuredResult
        ``.value`` (validated), ``.raw`` text, ``.attempts``, ``.repaired``.

    Raises
    ------
    ValidationError
        If the model never produces schema-valid JSON within ``max_repairs``.
    """

    client = client or LLMClient()
    model = model or _DEFAULT_STRUCTURED_MODEL

    base_system = _instruction(schema)
    system_text = f"{system}\n\n{base_system}" if system else base_system

    messages: list[Message] = [Message("user", prompt)]
    last_text = ""
    last_error = ""

    for attempt in range(max_repairs + 1):
        request = ChatRequest(
            model=model,
            messages=tuple(messages),
            system=system_text,
            max_tokens=max_tokens,
            effort=effort,
        )
        response = client.complete(request)
        last_text = response.text

        try:
            data = extract_json(last_text)
            value = validate(data, schema)
            return StructuredResult(
                value=value,
                raw=last_text,
                attempts=attempt + 1,
                repaired=attempt > 0,
            )
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)
            if attempt == max_repairs:
                break
            # Feed the failure back for a repair round.
            messages.append(Message("assistant", last_text))
            messages.append(Message("user", _repair_instruction(last_text, last_error)))

    raise ValidationError(
        f"could not obtain schema-valid output after {max_repairs + 1} attempt(s): "
        f"{last_error}",
        details={"last_output": last_text[:500]},
    )


__all__ = [
    "complete_structured",
    "StructuredResult",
    "Schema",
    "extract_json",
    "validate",
    "json_schema_of",
]
