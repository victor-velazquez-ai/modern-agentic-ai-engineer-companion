"""Rolling summarization for working-memory compaction (Ch 14).

When the working window overflows its token budget, the oldest turns are folded into a *rolling
summary* instead of being dropped. That summary is produced by a :class:`Summarizer`.

In ``COMPANION_MOCK=1`` (the default) we use :class:`MockSummarizer`: a deterministic, offline,
extractive summarizer that costs nothing and makes tests reproducible. In production you inject a
summarizer backed by the platform ``llm/`` gateway — the contract is just the :class:`Summarizer`
protocol, so the swap is one line at construction time. ``default_summarizer`` honors the MOCK
switch and **fails loudly** under ``MOCK=0`` rather than silently spending; the live path must be
injected explicitly. Secrets are read from the environment only (by the gateway, never here).
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from .working import Message


@runtime_checkable
class Summarizer(Protocol):
    """Turn a batch of conversation turns (plus the prior summary) into a new summary.

    Implementations must be pure with respect to their inputs so working-memory compaction stays
    testable. A live implementation calls a model through the ``llm/`` gateway; the mock below is
    the offline default.
    """

    def summarize(
        self, prior_summary: str, messages: list["Message"], *, max_chars: int | None = None
    ) -> str:
        """Return the new rolling summary covering ``prior_summary`` + ``messages``.

        ``max_chars`` is a soft size budget passed by the caller (working memory derives it from
        the token budget) so the rolling summary can never itself outgrow the window it compacts.
        Implementations should honor it best-effort.
        """
        ...


class MockSummarizer:
    """Deterministic, offline summarizer — no API spend, stable output for tests.

    It is intentionally *extractive*: it keeps the most salient sentence-ish fragment from each
    evicted turn and threads them onto the prior summary. That is enough to (a) prove the
    compaction path works end to end and (b) preserve recalled facts across a restart in the demo,
    without pretending to be a real LLM. Swap in a gateway-backed summarizer for real prose.
    """

    #: default cap when the caller doesn't pass one (keeps the summary bounded regardless)
    max_chars: int = 600

    def summarize(
        self, prior_summary: str, messages: list["Message"], *, max_chars: int | None = None
    ) -> str:
        cap = max_chars if max_chars is not None else self.max_chars
        cap = max(40, cap)  # never collapse the summary to nothing
        fragments: list[str] = []
        if prior_summary:
            fragments.append(prior_summary.strip())
        for msg in messages:
            salient = self._salient_fragment(msg.content)
            if salient:
                fragments.append(f"{msg.role}: {salient}")
        summary = " | ".join(f for f in fragments if f)
        if len(summary) > cap:
            # keep the tail — the most recent context is the most useful to retain
            summary = "…" + summary[-(cap - 1) :]
        return summary

    @staticmethod
    def _salient_fragment(text: str) -> str:
        """Pick a compact, information-bearing fragment from one turn."""
        text = text.strip()
        if not text:
            return ""
        # First sentence is usually the point; fall back to the first ~120 chars.
        sentences = re.split(r"(?<=[.!?])\s+", text)
        fragment = sentences[0].strip()
        if len(fragment) > 120:
            fragment = fragment[:117].rstrip() + "…"
        return fragment


class EchoSummarizer:
    """A trivial summarizer used when summarization is disabled — concatenates roles only.

    Not used by default; handy in tests that want to assert "a summary happened" cheaply.
    """

    def summarize(
        self, prior_summary: str, messages: list["Message"], *, max_chars: int | None = None
    ) -> str:
        roles = ", ".join(m.role for m in messages)
        head = f"{prior_summary} " if prior_summary else ""
        summary = f"{head}[compacted {len(messages)} turns: {roles}]".strip()
        if max_chars is not None and len(summary) > max_chars:
            summary = "…" + summary[-(max(40, max_chars) - 1) :]
        return summary


def default_summarizer() -> Summarizer:
    """Return the summarizer chosen by the environment.

    ``COMPANION_MOCK`` defaults to ``"1"`` (mock). Under ``MOCK=0`` the live path would construct a
    gateway-backed summarizer here; until one is injected we fail loud rather than silently spend.
    """
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    if mock:
        return MockSummarizer()
    # Live seam: a ``GatewaySummarizer`` over the platform ``llm/`` gateway would go here. Until it
    # is wired in, fail loudly so a MOCK=0 run never silently spends or silently mocks.
    raise RuntimeError(
        "COMPANION_MOCK=0 requested a live summarizer, but no llm/ gateway summarizer is wired "
        "in. Inject a Summarizer explicitly (see README §Live path) or run with COMPANION_MOCK=1."
    )
