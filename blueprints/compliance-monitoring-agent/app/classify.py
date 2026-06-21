"""classify — structured, confidence-bearing classification via the ``agent-loop`` blueprint.

This is the "decide" step of the screener (book **Ch 15 — Structured outputs**): given one
monitored item *and the policy rule retrieval surfaced as its likely basis*, produce a
schema-validated verdict — ``label`` (clear / flag), a ``confidence`` in ``[0, 1]``, the
``rule_id`` it cites, and a short ``reason`` — never free-form prose.

How it composes ``agent-loop``: we run the item through an :class:`AgentLoop` whose only tool is
``record_assessment``. The model's *single legitimate move* is to call that tool with a
schema-shaped argument object; the tool validates and captures it. That is exactly the agent-loop
pattern's "tool call as the structured-output channel" — the loop's malformed-call repair and
turn cap come for free, and the captured assessment is what we trust.

Under ``COMPANION_MOCK=1`` (default) the model is a deterministic stand-in: a keyword + retrieval
heuristic that decides clear/flag and emits the tool call. It spends nothing and is reproducible.
Under ``COMPANION_MOCK=0`` you inject a real ``ModelPort`` (an ``llm-gateway`` client) and the
*same* loop, tool schema, and validation drive the live model — the wiring does not change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from . import add_blueprint_paths
from .policy_check import PolicyMatch

add_blueprint_paths()

from agent_loop import (  # noqa: E402  (path wired above)
    AgentLoop,
    ModelPort,
    ToolCall,
    ToolRegistry,
    assistant,
    tool,
)
from agent_loop.model import MockModel  # noqa: E402

LABELS = ("clear", "flag")

# Keyword -> rule prior. Cheap, transparent signal the MOCK "brain" uses to decide flag vs clear
# and to sanity-check retrieval. A real model replaces this; the schema/validation are unchanged.
_VIOLATION_CUES: dict[str, tuple[str, ...]] = {
    "COMM-01": ("ssn", "social security", "account number", "card number", "dob", "passport"),
    "COMM-02": ("guarantee", "guaranteed", "risk-free", "double your money", "no risk"),
    "COMM-03": ("mnpi", "non-public", "unannounced", "merger", "acquisition", "insider"),
    "COMM-04": ("idiot", "hate", "slur", "harass", "shut up", "threat"),
    "TXN-01": ("10,000", "10000", "$9,9", "structur", "split the payment", "just under"),
    "TXN-02": ("sanction", "ofac", "prohibited jurisdiction", "blocked entity", "high-risk"),
    "TXN-03": ("duplicate", "personal expense", "no receipt", "missing receipt", "reimburse"),
}


@dataclass(frozen=True)
class Assessment:
    """A schema-validated classification verdict for one item.

    ``label`` is one of :data:`LABELS`; ``confidence`` is in ``[0, 1]``; ``rule_id`` is the policy
    rule cited (empty when ``clear``); ``reason`` is one human-readable line. This is the object
    routing and the audit log consume.
    """

    label: str
    confidence: float
    rule_id: str
    reason: str

    @property
    def flagged(self) -> bool:
        return self.label == "flag"


# The JSON schema the model's tool call must satisfy — this is the structured-output contract.
ASSESSMENT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "confidence": {"type": "number"},
        "rule_id": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["label", "confidence", "rule_id", "reason"],
}


def _heuristic_assessment(item_text: str, match: PolicyMatch) -> Assessment:
    """Deterministic clear/flag decision for MOCK mode (no model, no spend).

    Logic: if the item text contains a violation cue for the *retrieved* rule (or the retrieval
    landed on a non-benign rule with strong score), flag it citing that rule; otherwise clear.
    Confidence blends cue strength and retrieval score so it is bounded and explainable.
    """
    text = item_text.lower()
    rule_id = match.rule_id
    cues = _VIOLATION_CUES.get(rule_id, ())
    cue_hits = sum(1 for c in cues if c in text)

    if match.benign and cue_hits == 0:
        return Assessment(
            label="clear",
            confidence=round(min(0.6 + match.score, 0.95), 3),
            rule_id="",
            reason="Routine business activity; no policy rule indicates a violation.",
        )

    # Non-benign retrieval and/or explicit cue -> flag, citing the retrieved rule.
    cue_strength = min(cue_hits / 2.0, 1.0)
    retrieval_strength = min(match.score / 2.0, 1.0)
    confidence = round(0.5 + 0.5 * max(cue_strength, retrieval_strength), 3)
    reason = (
        f"Item appears to violate {rule_id} ({match.title}); "
        f"matched {cue_hits} policy cue(s) and retrieval grounded the rule."
    )
    return Assessment(label="flag", confidence=confidence, rule_id=rule_id, reason=reason)


def _mock_brain(item_text: str, match: PolicyMatch) -> Callable[[list], object]:
    """Build a scripted MockModel step that 'decides' then calls ``record_assessment``.

    The returned callable is an ``agent-loop`` ScriptStep: it produces the assistant turn whose
    single tool call carries the heuristic assessment. The loop dispatches that call to the
    ``record_assessment`` tool, which validates + captures it — same path a live model would take.
    """
    a = _heuristic_assessment(item_text, match)

    def step(_transcript: list) -> object:
        return assistant(
            text="Recording compliance assessment.",
            tool_calls=(
                ToolCall(
                    id="assess-1",
                    name="record_assessment",
                    arguments={
                        "label": a.label,
                        "confidence": a.confidence,
                        "rule_id": a.rule_id,
                        "reason": a.reason,
                    },
                ),
            ),
        )

    return step


class Classifier:
    """Runs the structured classification pass for one item by composing the ``agent-loop``.

    The classifier owns a tiny tool registry (just ``record_assessment``) and an
    :class:`AgentLoop`. Each :meth:`assess` call runs the loop once: the model (mock or live)
    must call the tool with a schema-valid assessment, which the tool captures into ``_captured``.
    Validation lives in the tool, so a malformed verdict becomes a tool error the loop can surface
    rather than a crash.
    """

    def __init__(self, *, model: ModelPort | None = None) -> None:
        self._model = model  # None -> built per-item in MOCK mode; injected for the live path.
        self._captured: Assessment | None = None

        @tool(
            "record_assessment",
            "Record the final compliance assessment for the item under review.",
            ASSESSMENT_SCHEMA,
        )
        def record_assessment(
            label: str, confidence: float, rule_id: str = "", reason: str = ""
        ) -> str:
            self._captured = _validate_assessment(label, confidence, rule_id, reason)
            return f"recorded: {self._captured.label} ({self._captured.confidence:.2f})"

        self._tools = ToolRegistry([record_assessment])

    def assess(self, item_text: str, match: PolicyMatch) -> Assessment:
        """Classify one item, grounded by its retrieved policy ``match``.

        Returns the captured :class:`Assessment`. If the model never produced a valid tool call
        (a misbehaving live model), we fall back to a low-confidence ``clear`` with a reason rather
        than raising — a screener must degrade safely, and a human still reviews flagged volume.
        """
        self._captured = None
        if self._model is not None:
            model: ModelPort = self._model
        else:
            # MOCK: a scripted model that records the heuristic assessment via the tool.
            model = MockModel(script=[_mock_brain(item_text, match)])

        loop = AgentLoop(model=model, tools=self._tools, max_turns=3)
        prompt = _build_prompt(item_text, match)
        loop.run(prompt, system_prompt=_SYSTEM_PROMPT)

        if self._captured is not None:
            return self._captured
        return Assessment(
            label="clear",
            confidence=0.2,
            rule_id="",
            reason="Model returned no valid assessment; defaulted to clear for human review.",
        )


_SYSTEM_PROMPT = (
    "You are a compliance screening assistant. You review one item against the single most "
    "relevant policy rule and call record_assessment exactly once with a label (clear|flag), a "
    "confidence in [0,1], the cited rule_id, and a one-line reason. You flag; humans adjudicate."
)


def _build_prompt(item_text: str, match: PolicyMatch) -> str:
    """The per-item instruction handed to the model, carrying the retrieved rule as context."""
    return (
        "ITEM UNDER REVIEW:\n"
        f"{item_text}\n\n"
        "MOST RELEVANT POLICY RULE (retrieved):\n"
        f"[{match.rule_id}] {match.title}\n{match.snippet}\n\n"
        "Decide clear vs flag and call record_assessment."
    )


def _validate_assessment(
    label: str, confidence: float, rule_id: str, reason: str
) -> Assessment:
    """Coerce + validate a tool-call payload into an :class:`Assessment` (raises on bad shape).

    The agent-loop turns a raised exception here into a tool-error result the model can read and
    retry, so validation failures are recoverable rather than fatal.
    """
    if label not in LABELS:
        raise ValueError(f"label must be one of {LABELS}, got {label!r}")
    try:
        conf = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"confidence must be a number, got {confidence!r}") from exc
    conf = max(0.0, min(1.0, conf))
    rid = (rule_id or "").strip()
    if label == "flag" and not re.match(r"^[A-Z]+-\d+$", rid):
        raise ValueError("a 'flag' assessment must cite a rule_id like 'COMM-01'")
    return Assessment(label=label, confidence=conf, rule_id=rid, reason=(reason or "").strip())
