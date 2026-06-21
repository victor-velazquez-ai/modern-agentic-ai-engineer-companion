"""Compose gathered evidence into a structured, **cited** brief (Ch 15).

The synthesizer turns the workers' evidence into the product: a brief made of **claims**, where
*every claim links to the source it came from*. Citations are not a footnote here — they are the
deliverable. The structure mirrors how an analyst writes a memo: one section per sub-question,
each section a few sentences, each sentence carrying its ``[source-id]`` marker.

MOCK behavior
-------------
To stay free and deterministic, the synthesizer does **extractive** synthesis: it pulls the most
salient sentence(s) from each piece of evidence and attaches that evidence's source id, rather
than asking a model to write prose. That keeps every claim trivially grounded (the claim text is
*lifted from* a retrieved snippet), which is exactly the property the reflection pass and the
faithfulness evals check. On the live path you would swap :func:`synthesize` for a model call
(through ``llm-gateway``) that writes prose **and emits inline citations**, then run the same
reflection pass to verify it — the contract (a :class:`CitedBrief` of :class:`CitedClaim`s) is
unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .workers import Evidence

# A "sentence" for extraction: split on sentence-ending punctuation followed by space/eol.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Sentences that carry a concrete fact tend to contain a number, a percent, a unit, or a
# proper noun. We prefer those when picking a claim out of a passage.
_FACTY = re.compile(r"\d|percent|%|million|billion|SOC|ARR|CAGR|NRR|CAC", re.I)


@dataclass(frozen=True)
class CitedClaim:
    """A single assertion in the brief, with the source ids that ground it.

    ``citations`` is the set of source ids backing this claim — empty means **uncited**, which
    the reflection pass treats as a failure. ``evidence_snippet`` is the supporting text the
    claim was drawn from, kept so verification can check the claim against its source.
    """

    text: str
    citations: tuple[str, ...]
    facet: str
    evidence_snippet: str = ""

    @property
    def is_cited(self) -> bool:
        return bool(self.citations)

    def rendered(self) -> str:
        """The claim as it appears in the brief: text followed by its ``[id]`` markers."""
        marks = " ".join(f"[{c}]" for c in self.citations)
        return f"{self.text} {marks}".strip()


@dataclass(frozen=True)
class BriefSection:
    """One section of the brief: a sub-question and the cited claims that answer it."""

    facet: str
    heading: str
    claims: tuple[CitedClaim, ...]


@dataclass(frozen=True)
class CitedBrief:
    """The synthesized deliverable: sections of cited claims plus the source list."""

    question: str
    sections: tuple[BriefSection, ...]
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def claims(self) -> tuple[CitedClaim, ...]:
        """Every claim across all sections, flattened."""
        return tuple(c for s in self.sections for c in s.claims)

    @property
    def uncited_claims(self) -> tuple[CitedClaim, ...]:
        return tuple(c for c in self.claims if not c.is_cited)

    def render(self) -> str:
        """Render the brief as Markdown — headings, cited bullets, and a Sources list."""
        lines = [f"# Research brief: {self.question}", ""]
        for section in self.sections:
            lines.append(f"## {section.heading}")
            if not section.claims:
                lines.append("_No supporting evidence retrieved._")
            for claim in section.claims:
                lines.append(f"- {claim.rendered()}")
            lines.append("")
        if self.sources:
            lines.append("## Sources")
            for sid in self.sources:
                lines.append(f"- [{sid}]")
        return "\n".join(lines).rstrip() + "\n"


def _best_sentence(snippet: str) -> str:
    """Pick the most fact-bearing sentence from a snippet (prefers one with numbers/units)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(snippet.strip()) if s.strip()]
    if not sentences:
        return snippet.strip()
    facty = [s for s in sentences if _FACTY.search(s)]
    pool = facty or sentences
    # Shortest fact-bearing sentence: tight, quotable, and least likely to drift from its source.
    return min(pool, key=len)


def synthesize(
    question: str,
    evidence_by_facet: Mapping[str, Sequence[Evidence]],
    *,
    headings: Mapping[str, str] | None = None,
    max_claims_per_section: int = 2,
) -> CitedBrief:
    """Build a :class:`CitedBrief` from per-sub-question evidence.

    Args:
        question: the top-level research question (the brief's title).
        evidence_by_facet: ``{facet_id: [Evidence, ...]}`` produced by the workers.
        headings: optional ``{facet_id: human heading}`` map (defaults to a title-cased id).
        max_claims_per_section: cap on claims per sub-question so the brief stays a *brief*.

    Returns:
        A :class:`CitedBrief` whose every claim carries the source id of the evidence it was
        extracted from — so grounding is true by construction in MOCK mode.
    """
    headings = headings or {}
    sections: list[BriefSection] = []
    all_sources: list[str] = []
    seen_sources: set[str] = set()

    for facet, evidence in evidence_by_facet.items():
        claims: list[CitedClaim] = []
        for ev in list(evidence)[:max_claims_per_section]:
            sentence = _best_sentence(ev.snippet)
            claims.append(
                CitedClaim(
                    text=sentence,
                    citations=(ev.source_id,),
                    facet=facet,
                    evidence_snippet=ev.snippet,
                )
            )
            if ev.source_id not in seen_sources:
                seen_sources.add(ev.source_id)
                all_sources.append(ev.source_id)
        heading = headings.get(facet, facet.replace("-", " ").replace("_", " ").title())
        sections.append(
            BriefSection(facet=facet, heading=heading, claims=tuple(claims))
        )

    return CitedBrief(
        question=question,
        sections=tuple(sections),
        sources=tuple(all_sources),
    )
