"""The verification / reflection pass: flag uncited or unsupported claims (Ch 16).

A draft brief is not trustworthy until every claim has been checked **against its cited source**.
This pass is the agent's self-critique step (the reflection loop from Ch 16): for each claim it
asks two questions —

1. **Is it cited at all?** A claim with no ``[source-id]`` is an automatic failure — for due
   diligence an uncited assertion is worse than no assertion.
2. **Does the cited source actually support it?** We check that the claim's content words appear
   in the snippet the citation points to (a *grounding* check). A claim that cites a source which
   does not contain its terms is **unsupported** — a hallucinated citation — and is flagged.

The grounding check reuses ``rag-pipeline``'s shared tokenizer so "supported" means the same
thing here as it does in retrieval and reranking. The check is intentionally conservative and
deterministic; on the live path you would *additionally* run an LLM-judge (from ``eval-harness``)
for semantic entailment. The two are complementary: this catches the cheap, common failure
(citation doesn't mention the claim) for free, before spending a judge call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import _compose  # noqa: F401 — side effect: puts sibling src/ on sys.path
from .synthesize import CitedBrief, CitedClaim
from .workers import Evidence

# Reuse the pipeline's tokenizer so grounding uses the same word boundaries as retrieval.
from rag_pipeline.tokenize import tokens as _tokens  # type: ignore  # noqa: E402

# Content words only: drop high-frequency function words so "supported" measures whether the
# *meaningful* terms of a claim appear in its source, not whether both contain "the".
_STOPWORDS = frozenset(
    """a an and are as at be by do does for from has have how in is it its of on or that the
    this to was were what when where which who why with about over under into than then""".split()
)

# Fraction of a claim's content words that must appear in its cited source for it to count as
# grounded. 0.6 tolerates paraphrase/extraction noise while still catching a citation that has
# nothing to do with the claim.
DEFAULT_GROUNDING_THRESHOLD = 0.6


@dataclass(frozen=True)
class Claim:
    """A claim's verification verdict.

    ``status`` is one of ``"supported"``, ``"uncited"``, or ``"unsupported"``. ``grounding`` is
    the fraction of the claim's content words found in its cited source (``0.0`` when uncited).
    ``reason`` is a one-line human explanation surfaced in the report.
    """

    text: str
    citations: tuple[str, ...]
    status: str
    grounding: float
    reason: str

    @property
    def ok(self) -> bool:
        return self.status == "supported"


@dataclass(frozen=True)
class ReflectionReport:
    """The result of verifying every claim in a brief."""

    claims: tuple[Claim, ...]
    grounding_threshold: float = DEFAULT_GROUNDING_THRESHOLD

    @property
    def total(self) -> int:
        return len(self.claims)

    @property
    def supported(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.status == "supported")

    @property
    def uncited(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.status == "uncited")

    @property
    def unsupported(self) -> tuple[Claim, ...]:
        return tuple(c for c in self.claims if c.status == "unsupported")

    @property
    def flagged(self) -> tuple[Claim, ...]:
        """Every claim that failed verification (uncited or unsupported)."""
        return tuple(c for c in self.claims if not c.ok)

    @property
    def faithfulness(self) -> float:
        """Fraction of claims that are supported by a cited source. The headline metric."""
        if not self.claims:
            return 0.0
        return len(self.supported) / len(self.claims)

    @property
    def all_grounded(self) -> bool:
        return not self.flagged

    def render(self) -> str:
        """A compact verification summary for the console / CI logs."""
        lines = [
            "Reflection / verification pass",
            "-" * 40,
            f"claims      : {self.total}",
            f"supported   : {len(self.supported)}/{self.total}",
            f"faithfulness: {self.faithfulness:.0%}  "
            f"(grounding threshold {self.grounding_threshold:.0%})",
        ]
        if self.flagged:
            lines.append("")
            lines.append("Flagged claims:")
            for c in self.flagged:
                lines.append(f"  ! [{c.status}] {c.text[:72]}  — {c.reason}")
        else:
            lines.append("All claims grounded in a cited source.")
        return "\n".join(lines)


def _content_words(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in _STOPWORDS}


def _grounding(claim_text: str, source_text: str) -> float:
    """Fraction of the claim's content words present in the source snippet."""
    claim_words = _content_words(claim_text)
    if not claim_words:
        return 0.0
    source_words = _content_words(source_text)
    return len(claim_words & source_words) / len(claim_words)


def _verify_claim(
    claim: CitedClaim,
    evidence_by_source: Mapping[str, Evidence],
    *,
    threshold: float,
) -> Claim:
    """Verify one claim against the source(s) it cites."""
    if not claim.citations:
        return Claim(
            text=claim.text,
            citations=(),
            status="uncited",
            grounding=0.0,
            reason="claim has no citation",
        )

    # A claim may cite several sources; it is grounded if its best-matching source clears the bar.
    best = 0.0
    missing: list[str] = []
    for sid in claim.citations:
        ev = evidence_by_source.get(sid)
        source_text = claim.evidence_snippet or (ev.snippet if ev else "")
        if ev is None and not claim.evidence_snippet:
            missing.append(sid)
            continue
        best = max(best, _grounding(claim.text, source_text))

    if missing and best == 0.0:
        return Claim(
            text=claim.text,
            citations=claim.citations,
            status="unsupported",
            grounding=0.0,
            reason=f"cited source(s) {missing!r} not found in retrieved evidence",
        )
    if best >= threshold:
        return Claim(
            text=claim.text,
            citations=claim.citations,
            status="supported",
            grounding=best,
            reason=f"grounded ({best:.0%} of claim terms in cited source)",
        )
    return Claim(
        text=claim.text,
        citations=claim.citations,
        status="unsupported",
        grounding=best,
        reason=f"cited source supports only {best:.0%} of claim terms "
        f"(< {threshold:.0%} threshold)",
    )


def reflect(
    brief: CitedBrief,
    evidence: Sequence[Evidence],
    *,
    grounding_threshold: float = DEFAULT_GROUNDING_THRESHOLD,
) -> ReflectionReport:
    """Verify every claim in ``brief`` against the retrieved ``evidence``.

    Args:
        brief: the synthesized brief to check.
        evidence: all evidence the workers gathered (used to resolve a citation's source text).
        grounding_threshold: minimum fraction of a claim's content words that must appear in its
            cited source for the claim to count as supported.

    Returns:
        A :class:`ReflectionReport`. ``report.flagged`` is the list of claims a human must fix;
        ``report.faithfulness`` is the headline metric the evals gate on.
    """
    evidence_by_source = {ev.source_id: ev for ev in evidence}
    verified = tuple(
        _verify_claim(c, evidence_by_source, threshold=grounding_threshold)
        for c in brief.claims
    )
    return ReflectionReport(claims=verified, grounding_threshold=grounding_threshold)
