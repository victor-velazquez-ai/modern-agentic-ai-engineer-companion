"""Call -> CRM: structured extraction of outcomes/next steps into fields (composes ``agent-loop``).

A rep finishes a call; this stage turns the recording/notes into a *structured, confidence-scored*
CRM update and writes it **conservatively** through the MCP boundary. It is the Ch 15 pattern
(structured field extraction) running on the Ch 12 ``agent-loop``:

1. an :class:`~agent_loop.AgentLoop` is given one tool — ``crm_update_fields`` (the guarded MCP
   write, surfaced as an agent tool);
2. a deterministic, offline "extractor brain" (a scripted ``MockModel``) reads the transcript and
   emits **one** tool call whose arguments are the proposed fields, each tagged with a confidence;
3. the loop dispatches the call; the CRM boundary applies the conservative-write policy (writes
   high-confidence non-empty fields, *flags* the rest); the tool result comes back as the answer.

Why a real loop instead of one function call? Because in production the "brain" is an LLM that may
need several turns (read the account, extract, reconcile) and may emit a malformed call — exactly
the cases the ``agent-loop`` blueprint hardens. Swapping the mock for a gateway-backed
``ModelPort`` is a one-line change (``COMPANION_MOCK=0``); the loop, the tool, and the policy are
unchanged. Here the brain is deterministic so the demo and the eval set are reproducible and free.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from revops.compose import ensure_on_path

ensure_on_path()

from agent_loop import (  # noqa: E402
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
    tool as tool_decorator,
)

from tools.crm_mock import CRMStore, connect_crm  # noqa: E402


@dataclass(frozen=True)
class ExtractionField:
    """One proposed CRM field with the model's confidence in it (0..1)."""

    name: str
    value: Any
    confidence: float


# --- the deterministic "extractor brain" -------------------------------------------------------
#
# This stands in for an LLM doing structured extraction. It is rule-based so the blueprint runs
# free and the eval set is reproducible; the *shape* of its output (confidence-scored fields) is
# exactly what a real extraction prompt is asked to return.


_AMOUNT_RE = re.compile(r"(?:\$|around |about )?\s*([0-9]{2,3})[\s,]*(?:thousand|k\b|,000)", re.I)
_FUZZY_AMOUNT = re.compile(r"\b(forty[- ]?eight|fifty|sixty|seventy)\b", re.I)
_WORD_TO_K = {"forty-eight": 48, "fortyeight": 48, "fifty": 50, "sixty": 60, "seventy": 70}


def _detect_amount(text: str) -> ExtractionField | None:
    t = text.lower()
    m = _AMOUNT_RE.search(t)
    if m:
        return ExtractionField("amount", int(m.group(1)) * 1000, 0.7)
    w = _FUZZY_AMOUNT.search(t)
    if w:
        key = w.group(1).replace(" ", "-")
        thousands = _WORD_TO_K.get(key)
        if thousands is not None:
            # If the buyer hedged ("need finance sign-off", "still need to get ... to sign off"),
            # the number is soft -> low confidence -> the CRM boundary will flag, not write it.
            hedged = any(
                h in t
                for h in ("sign off", "sign-off", "need to get", "thinking", "somewhere around")
            )
            return ExtractionField("amount", thousands * 1000, 0.6 if hedged else 0.85)
    return None


def _detect_next_step(text: str) -> ExtractionField | None:
    # Pull the rep's stated next step. We look for an explicit "next step" cue, else the last
    # "I'll ..." commitment from the rep — high precision, since a wrong next_step misleads RevOps.
    for line in text.splitlines():
        low = line.lower()
        if "next step" in low and " - " in line:
            step = line.split(" - ", 1)[1].strip().rstrip(".")
            return ExtractionField("next_step", step, 0.9)
    sends = re.findall(r"i'?ll (send[^.\n]+|get[^.\n]+over[^.\n]*)", text, flags=re.I)
    if sends:
        return ExtractionField("next_step", sends[-1].strip().rstrip(".").capitalize(), 0.8)
    return None


def _detect_stage(text: str) -> ExtractionField | None:
    t = text.lower()
    if "buy rather than build" in t or "buy vs build" in t or "we're going to buy" in t:
        return ExtractionField("stage", "Evaluation", 0.8)
    if "sign" in t and ("end of july" in t or "before the end" in t):
        return ExtractionField("stage", "Negotiation", 0.78)
    return None


def extract_fields(transcript: str) -> list[ExtractionField]:
    """Deterministically extract confidence-scored CRM fields from a call transcript.

    Returns proposals only; *whether each is written* is the CRM boundary's decision (conservative
    write). Detectors are deliberately high-precision: it is better to surface nothing for a field
    than to write a wrong value into the forecast.
    """
    out: list[ExtractionField] = []
    for detector in (_detect_amount, _detect_next_step, _detect_stage):
        field = detector(transcript)
        if field is not None:
            out.append(field)
    return out


def _extractor_model(transcript: str) -> MockModel:
    """A two-step scripted model: (1) emit the extraction as a tool call, (2) summarise the result.

    Step 1 is a literal assistant turn carrying one ``crm_update_fields`` call. Step 2 is a
    *callable* step that reads the tool result off the transcript and phrases the final answer —
    the same react-to-tool-output shape a real model uses.
    """
    fields = extract_fields(transcript)
    return MockModel(
        [
            assistant(
                text="Extracting call outcomes into CRM fields.",
                tool_calls=(
                    ToolCall(
                        id="x1",
                        name="crm_update_fields",
                        arguments={
                            "fields": {
                                f.name: {"value": f.value, "confidence": f.confidence}
                                for f in fields
                            }
                        },
                    ),
                ),
            ),
            lambda hist: assistant(text=hist[-1].text),  # echo the write report as the answer
        ]
    )


@dataclass(frozen=True)
class CallToCRMResult:
    """The outcome of processing one call into the CRM."""

    account_id: str
    proposed: list[ExtractionField]
    write_report: dict[str, Any]

    @property
    def applied(self) -> dict[str, Any]:
        return dict(self.write_report.get("applied", {}))

    @property
    def flagged(self) -> list[dict[str, Any]]:
        return list(self.write_report.get("flagged", []))


def process_call(
    call: Mapping[str, Any],
    *,
    store: CRMStore | None = None,
    min_confidence: float = 0.75,
) -> CallToCRMResult:
    """Run one call record through the extraction loop and the conservative CRM write.

    ``call`` is a record like ``data/calls/*.json`` (``account_id`` + ``transcript``). The CRM
    write goes through the **guarded MCP client** (``crm_update_fields``), so the conservative
    policy and the schema validation apply exactly as they would against a real CRM.
    """
    store = store or CRMStore()
    account_id = str(call["account_id"])
    transcript_text = str(call["transcript"])

    client = connect_crm(store)

    # Wrap the guarded MCP write as an agent-loop tool. The closure binds account_id and the
    # confidence floor so the model only has to decide the *fields*, not the routing.
    @tool_decorator(
        "crm_update_fields",
        "Conservatively write confidence-scored CRM fields for the current account.",
        {
            "type": "object",
            "properties": {"fields": {"type": "object"}},
            "required": ["fields"],
        },
    )
    def crm_update_fields(fields: dict[str, Any]) -> str:
        report = client.call(
            "crm_update_fields",
            {
                "account_id": account_id,
                "fields": fields,
                "min_confidence": min_confidence,
            },
        )
        return json.dumps(report, sort_keys=True)

    loop = AgentLoop(
        model=_extractor_model(transcript_text),
        tools=ToolRegistry([crm_update_fields]),
        max_turns=4,
    )
    result = loop.run(
        f"Extract CRM updates from this call and write them conservatively:\n{transcript_text}",
        system_prompt=(
            "You are a RevOps extraction agent. Extract only what the call explicitly supports, "
            "attach a confidence to each field, and write conservatively. Never guess."
        ),
    )

    report = json.loads(result.output) if result.output else {"applied": {}, "flagged": []}
    return CallToCRMResult(
        account_id=account_id,
        proposed=extract_fields(transcript_text),
        write_report=report,
    )
