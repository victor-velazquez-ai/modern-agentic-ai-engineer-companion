"""The reflection / critique pass (Ch 16) — improve a draft before a human sees it.

Plain "draft once and ship" wastes the cheapest quality lever there is: have the model *critique
its own draft against a rubric, then revise*. That is the reflection pattern from Ch 16, and it
is exactly the per-stage loop the ``agent-loop`` blueprint implements (observe -> decide -> act
-> observe). Here the "tools" are conceptual — critique and revise are two model turns — so we
drive the same :class:`agent_loop.MockModel` seam directly rather than a tool registry.

The point of composition: the critique loop is *the agent-loop blueprint's model port*, not a
re-implementation. In MOCK mode we script a deterministic critic; on the live path you inject an
``llm-gateway``-backed :class:`~agent_loop.model.ModelPort` and the loop is unchanged.

This module is deliberately small and dependency-light so the *structure* — critique against a
rubric, then revise — is the thing you read. A real build would expand the rubric and add a
second critique round; the seam supports both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .compose import ModelPort, assistant

# The default content rubric the critic scores a draft against. Anchored so the critique is
# specific ("the CTA is vague") rather than vibes ("could be better").
DEFAULT_RUBRIC = (
    "Critique this marketing draft on: (1) on-brand voice, (2) a single clear call to action, "
    "(3) only claims supported by the provided facts, (4) appropriate length for the channel. "
    "List concrete, actionable fixes — do not rewrite yet."
)


@dataclass(frozen=True, slots=True)
class CritiqueResult:
    """The output of one reflect-then-revise pass."""

    draft: str          # the input draft
    critique: str       # the critic's findings
    revised: str        # the improved draft
    changed: bool = field(default=False)

    @property
    def output(self) -> str:
        """The text to carry forward (the revision)."""
        return self.revised


# A "reviser" turns (draft, critique) into a revised draft. The default is the deterministic
# mock below; the live path injects a gateway-backed model turn here.
Reviser = Callable[[str, str], str]


def _mock_critique(draft: str, rubric: str) -> str:
    """A deterministic stand-in critic (no model, no spend).

    It does not call an LLM. It applies a few cheap, explainable heuristics that map onto the
    rubric so the *critique-then-revise* code path runs for free and identically every time. A
    live critic (a gateway-backed model turn) would replace just this function.
    """
    notes: list[str] = []
    lowered = draft.lower()
    if "call to action" not in lowered and not any(
        cta in lowered for cta in ("sign up", "get started", "learn more", "try ", "book a")
    ):
        notes.append("Add a single, explicit call to action.")
    if len(draft.split()) > 80:
        notes.append("Tighten: the draft is long for a short-form channel.")
    if "!" in draft:
        notes.append("Soften the hype punctuation to match a measured brand voice.")
    if not notes:
        notes.append("Draft is on-rubric; only light tightening needed.")
    return " ".join(f"- {n}" for n in notes)


def _mock_revise(draft: str, critique: str) -> str:
    """A deterministic reviser that applies the mock critique's cheap fixes.

    Mirrors what a model would do given the critique, but with no spend: drop hype punctuation,
    and append a clear CTA if the critique asked for one. Enough to show the draft *changing* as
    a result of the critique — the behaviour the reflection pattern is about.
    """
    revised = draft.replace("!", ".")
    if "call to action" in critique.lower():
        revised = revised.rstrip(". ") + ". Get started today."
    return revised.strip()


@dataclass(slots=True)
class CritiqueLoop:
    """Reflect-then-revise, composed over the agent-loop model seam.

    Parameters
    ----------
    model:
        An optional :class:`agent_loop.model.ModelPort`. When provided (the live path), critique
        and revision are real model turns driven through that port. When ``None`` (MOCK, the
        default), the deterministic stand-ins above run — free and reproducible.
    rubric:
        What the critic scores the draft against. Adapt for your channel/brand.
    reviser:
        Override the revision step (e.g. plug a different model turn) without touching the loop.
    """

    model: ModelPort | None = None
    rubric: str = DEFAULT_RUBRIC
    reviser: Reviser | None = None

    def run(self, draft: str) -> CritiqueResult:
        """Critique ``draft`` against the rubric, then revise it."""
        critique = self._critique(draft)
        revised = self._revise(draft, critique)
        return CritiqueResult(
            draft=draft,
            critique=critique,
            revised=revised,
            changed=revised.strip() != draft.strip(),
        )

    # -- the two model turns (or their offline stand-ins) -------------------------------
    def _critique(self, draft: str) -> str:
        if self.model is None:
            return _mock_critique(draft, self.rubric)
        prompt = f"{self.rubric}\n\nDRAFT:\n{draft}"
        return self._ask(prompt)

    def _revise(self, draft: str, critique: str) -> str:
        if self.reviser is not None:
            return self.reviser(draft, critique)
        if self.model is None:
            return _mock_revise(draft, critique)
        prompt = (
            "Revise the draft to address every point of the critique. Return only the revised "
            f"draft.\n\nCRITIQUE:\n{critique}\n\nDRAFT:\n{draft}"
        )
        return self._ask(prompt)

    def _ask(self, prompt: str) -> str:
        """One model turn through the injected port (live path only)."""
        # The agent-loop ModelPort.complete takes (transcript, tools); a single user turn with no
        # tools yields one assistant turn — exactly a one-shot completion.
        from agent_loop import user  # local import: only needed on the live path

        assert self.model is not None  # narrowed by callers
        response = self.model.complete([user(prompt)], [])
        return response.message.text


def make_critique_loop(model: ModelPort | None = None) -> CritiqueLoop:
    """Build the default critique loop. ``model=None`` -> offline MOCK critic + reviser."""
    return CritiqueLoop(model=model)
