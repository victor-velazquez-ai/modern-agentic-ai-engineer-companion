"""The extraction step — the agent-loop read, traced, with the repair loop wired in (Ch 45).

This is the module that turns a *document* into a *candidate record*. It is the composition
seam: it does not reimplement the agent loop, the tracer, or the gateway — it **imports** the
pattern blueprints (via :mod:`pipeline._compose`) and wires them together the way the PLAN
describes:

* **``agent-loop``** runs the vision/OCR read as a tool-using turn: a ``read_document`` tool
  parses the source into a draft JSON object, then the model returns it. The loop's hardening
  (turn cap, tool-error isolation, malformed-call repair) comes for free. On the live path you
  inject a vision-capable :class:`~agent_loop.ModelPort` backed by the ``llm-gateway``; here the
  default is a deterministic, offline :class:`~agent_loop.MockModel` so nothing spends.
* **``pipeline.repair``** wraps the loop with the validate → repair → re-validate policy: the
  ``reextract`` seam it needs is "run the loop again on a repair prompt", which is exactly what
  :func:`_make_reextract` returns.
* **``observability-stack``** wraps the whole per-item read in a span tree, so a backfill is
  auditable item by item (run → extract → each validate/repair step) with a cost roll-up. The
  tracer is optional: if the sibling is absent the pipeline degrades to a no-op and still runs.

The OCR/vision read is *mocked* by parsing a tiny, explicit document format (see
:mod:`pipeline` sample docs) instead of calling a model on a pixel buffer. That keeps the
blueprint free and deterministic while preserving the real seam — swap
:func:`build_mock_extractor_model` for a gateway-backed vision port and the loop, repair, and
tracing above are unchanged.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from . import _compose  # noqa: F401  -- side effect: pattern blueprints onto sys.path

# Composed pattern blueprints (imported after _compose wired sys.path).
from agent_loop import (  # noqa: E402
    AgentLoop,
    MockModel,
    ModelPort,
    ToolCall,
    ToolRegistry,
    assistant,
    tool,
)

try:  # observability is optional at runtime; degrade to a no-op tracer if the sibling is absent.
    from observability_stack import SpanKind, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover - exercised only when the sibling is missing
    SpanKind = None  # type: ignore[assignment]
    Tracer = None  # type: ignore[assignment]
    _HAVE_OBS = False

from .repair import RepairOutcome, attempt_repairs  # noqa: E402
from .schema import INVOICE_JSON_SCHEMA  # noqa: E402

# The model id the trace prices against. ``mock-model`` is $0 in the observability cost table,
# so a MOCK backfill rolls up to exactly $0.00 instead of an "unknown model" warning. On the
# live path this becomes the gateway-routed model (e.g. "claude-haiku-4" for a cheap read).
MOCK_MODEL_ID = "mock-model"


# --------------------------------------------------------------------------------------
# The agent-loop tool: the "vision/OCR read" seam.
# --------------------------------------------------------------------------------------
# In production the model is shown the document image and *emits* the structured fields; the
# tool is how the loop gives the read a typed, schema-shaped channel (Ch 12/45). Offline, the
# tool body deterministically parses our tiny sample-doc format so the demo shows a real
# tool-using turn with zero spend. The tool's JSON return is the draft the loop hands back.
@tool(
    "read_document",
    "Read the source document and return the extracted invoice fields as a JSON object "
    "matching the invoice schema. Call exactly once with the raw document source.",
    {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "The raw document source/OCR text."}
        },
        "required": ["source"],
    },
)
def _read_document(source: str) -> str:
    """Parse a sample document's ``KEY: value`` body into a draft invoice JSON object.

    This stands in for a vision model reading a scan. It is intentionally *lossy and literal* —
    it copies whatever the document says, errors and all — because the repair loop and the
    confidence scorer downstream are what catch and fix bad reads. A "smart" parser here would
    hide the very failure modes the pipeline exists to handle.
    """
    return json.dumps(parse_sample_document(source))


def parse_sample_document(source: str) -> dict[str, Any]:
    """Turn the mock document text format into a raw (unvalidated) extraction dict.

    Format (one field per line; ``LINE`` rows build ``line_items``)::

        invoice_number: INV-1001
        vendor: Acme Corp
        invoice_date: 2026-03-04
        currency: USD
        total: 240.00
        LINE: Widget | 2 | 60.00 | 120.00
        LINE: Gadget | 1 | 120.00 | 120.00

    Values are copied verbatim (a date in the wrong format stays wrong) so the validate/repair
    loop has something real to fix.
    """
    record: dict[str, Any] = {}
    line_items: list[dict[str, Any]] = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("LINE:"):
            parts = [p.strip() for p in line.split(":", 1)[1].split("|")]
            row: dict[str, Any] = {}
            keys = ("description", "quantity", "unit_price", "amount")
            for key, val in zip(keys, parts):
                row[key] = val
            line_items.append(row)
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        record[key.strip()] = val.strip()
    if line_items:
        record["line_items"] = line_items
    return record


# --------------------------------------------------------------------------------------
# The model seam: offline MockModel by default, a gateway-backed port on the live path.
# --------------------------------------------------------------------------------------
def build_mock_extractor_model(repaired_source: str | None = None) -> MockModel:
    """A deterministic 'brain' that calls ``read_document`` once, then returns its result.

    ``repaired_source`` lets a *repair* turn re-read a corrected source: the demo hands the loop
    a cleaned-up document on the second pass (the field the model "fixed" after seeing the
    validation errors), so the repaired branch is exercised without any spend. When it is
    ``None`` the model simply re-reads the original source.

    On the live path you replace this with a vision-capable port from the ``llm-gateway`` — the
    loop, the tool, the repair policy, and the tracing all stay the same (the Ch 45 seam).
    """

    def _decide(transcript: list[Any]) -> Any:
        # The source to read: the repaired version on a repair turn, else the latest user text.
        if repaired_source is not None:
            source = repaired_source
        else:
            last_user = next((m for m in reversed(transcript) if m.role == "user"), None)
            source = last_user.text if last_user else ""
        return assistant(
            text="Reading the document and extracting invoice fields.",
            tool_calls=(ToolCall(id="read-1", name="read_document", arguments={"source": source}),),
        )

    return MockModel(
        [
            _decide,  # turn 1: call the read tool
            lambda t: assistant(text=_last_tool_text(t)),  # turn 2: return the read JSON as the answer
        ]
    )


def _last_tool_text(transcript: list[Any]) -> str:
    """The content of the most recent tool result — the draft JSON the read tool produced."""
    for msg in reversed(transcript):
        if getattr(msg, "role", None) == "tool":
            return msg.text
    return "{}"


def default_extractor_model() -> ModelPort:
    """Pick the extractor model from the environment.

    ``COMPANION_MOCK`` defaults to ``"1"`` (offline, free, deterministic). Under ``MOCK=0`` a
    live path would build a vision-capable, gateway-backed port here; we ship only the mock and
    fail loud rather than spending tokens behind the caller's back — mirroring the agent-loop and
    eval-harness seams.
    """
    if os.getenv("COMPANION_MOCK", "1") != "0":
        return build_mock_extractor_model()
    raise RuntimeError(
        "COMPANION_MOCK=0 requested a live extractor, but no llm-gateway vision client is wired "
        "in. Inject a ModelPort (see README -> Live path) or run with COMPANION_MOCK=1."
    )


# --------------------------------------------------------------------------------------
# The composition: run the loop, decode its output, drive the repair policy, trace it all.
# --------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ExtractResult:
    """The outcome of extracting one document: the repair outcome plus the read it started from."""

    outcome: RepairOutcome
    first_pass: Any  # the decoded first-pass payload (for tracing / debugging)

    @property
    def ok(self) -> bool:
        return self.outcome.ok


def _run_read(model: ModelPort) -> Any:
    """Run the agent-loop read once and decode its JSON output into a Python object."""
    loop = AgentLoop(
        model=model,
        tools=ToolRegistry([_read_document]),
        max_turns=4,
    )
    system_prompt = (
        "You are a document-extraction agent. Read the document with the read_document tool and "
        "return ONLY the extracted invoice as a JSON object that fits the schema. Do not invent "
        "fields the document does not contain."
    )
    result = loop.run(_SCHEMA_HINT, system_prompt=system_prompt)
    return _decode(result.output)


_SCHEMA_HINT = (
    "Extract the invoice. Target JSON schema:\n"
    + json.dumps(INVOICE_JSON_SCHEMA, indent=2)
)


def _decode(text: str) -> Any:
    """Decode the loop's text output as JSON; on failure return the raw text for the validator.

    A non-JSON read is not a crash — :func:`~pipeline.schema.validate_invoice` will reject it with
    a structured "top level: expected an object" error, which the repair loop then tries to fix.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def _make_reextract(repaired_source: str | None) -> Callable[[str], Any]:
    """Build the ``reextract`` seam :func:`~pipeline.repair.attempt_repairs` calls per repair turn.

    Each repair turn re-runs the agent-loop read. In MOCK mode the repaired model re-reads a
    corrected source (``repaired_source``); on the live path the repair *prompt* (the field-
    addressed validation errors) is what the model conditions on. Either way the seam is
    ``(prompt) -> raw_payload`` and the policy in ``repair.py`` is untouched.
    """

    def reextract(_prompt: str) -> Any:
        model = build_mock_extractor_model(repaired_source=repaired_source)
        return _run_read(model)

    return reextract


def extract_document(
    source: str,
    *,
    model: ModelPort | None = None,
    repaired_source: str | None = None,
    max_repairs: int = 2,
    tracer: "Tracer | None" = None,
) -> ExtractResult:
    """Extract one document into a validated invoice (or a failed outcome), traced.

    Pipeline for one item:

    1. **read** (agent-loop) — run the loop with the ``read_document`` tool; decode its JSON.
    2. **validate → repair** (pipeline.repair) — validate the read; on failure, re-read with the
       errors fed back, up to ``max_repairs`` times.
    3. **trace** (observability-stack) — wrap the whole thing in spans when a tracer is supplied,
       emitting a model span for the read and recording each validate/repair step as an event.

    Args:
        source: the raw document source/OCR text.
        model: the extractor :class:`~agent_loop.ModelPort`. Defaults to the offline mock.
        repaired_source: in MOCK mode, the corrected source a repair turn should re-read. Lets the
            demo exercise the *repaired* branch deterministically; ignored on the live path.
        max_repairs: repair turns allowed after the first validation (0 disables repair).
        tracer: an optional ``observability_stack.Tracer`` for a per-item audit trace.

    Returns:
        An :class:`ExtractResult` carrying the :class:`~pipeline.repair.RepairOutcome`.
    """
    model = model or default_extractor_model()

    # The observability hook the repair loop calls on every validate/repair step. When a tracer
    # is active we add a child span per step so the trace shows exactly how many turns it took.
    span_cm = None
    if tracer is not None and _HAVE_OBS:
        span_cm = tracer.model_span(
            "extract.read",
            model=MOCK_MODEL_ID,
            input_tokens=0,
            output_tokens=0,
        )

    def on_event(name: str, payload: dict) -> None:
        if tracer is None or not _HAVE_OBS:
            return
        # Record each validate/repair as a short-lived child span (cheap, but it shows the
        # retry structure in the exported tree — the dead-letter visibility the PLAN wants).
        with tracer.span(f"{name}:attempt-{payload.get('attempt', '?')}", SpanKind.CHAIN):
            pass

    if span_cm is not None:
        with span_cm:
            first_pass = _run_read(model)
            outcome = attempt_repairs(
                first_pass,
                _make_reextract(repaired_source),
                max_repairs=max_repairs,
                on_event=on_event,
            )
    else:
        first_pass = _run_read(model)
        outcome = attempt_repairs(
            first_pass,
            _make_reextract(repaired_source),
            max_repairs=max_repairs,
            on_event=on_event,
        )

    return ExtractResult(outcome=outcome, first_pass=first_pass)
