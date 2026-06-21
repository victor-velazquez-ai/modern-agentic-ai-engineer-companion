"""Brand + compliance guardrails on the *output* (Ch 41).

The ``llm-gateway`` guards (Ch 41) protect the model boundary — PII redaction, injection, unsafe
input. This module is the *content-domain* layer that sits on top: it checks a finished draft or
variant against brand voice and compliance rules **before a human ever sees it**, and certainly
before anything is published.

Three rule families, all deterministic and offline (no model, no spend, reproducible in CI):

* **Forbidden language** — banned words/phrases (competitor slander, hype words your brand bans,
  slurs). A hard fail; these never ship.
* **Unsubstantiated claims** — superlatives and absolute promises ("guaranteed", "#1", "cure",
  "100%", "risk-free"). Fabricated product claims are a *legal* risk, not just a brand one, so
  the rule is conservative: flag the claim and require either a cited source or human sign-off.
* **Tone / required elements** — banned tone markers (ALL-CAPS shouting, excessive "!!!") and
  required disclaimers for regulated topics.

The output is a structured :class:`GuardrailReport`, not a raised exception: a flagged draft is
*routed to a human*, not destroyed. ``blocked`` is reserved for hard failures (forbidden
language) that must never reach review as-is.

Adapt this file to your domain: edit :data:`DEFAULT_RULES` (or pass your own
:class:`GuardrailRules`) with your forbidden list, your claim words, and your required
disclaimers. This is the file the PLAN's "edit guardrails.py for your forbidden language" step
points at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class Severity(str, Enum):
    """How serious a finding is — drives whether the run is blocked or just flagged."""

    BLOCK = "block"   # must never ship as-is (forbidden language)
    FLAG = "flag"     # needs human judgement (unsupported claim, tone)
    INFO = "info"     # advisory only

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GuardrailFinding:
    """One rule hit: what fired, where, and how serious."""

    rule: str
    severity: Severity
    message: str
    excerpt: str = ""

    def render(self) -> str:
        loc = f"  ‹{self.excerpt}›" if self.excerpt else ""
        return f"[{self.severity}] {self.rule}: {self.message}{loc}"


@dataclass(frozen=True, slots=True)
class GuardrailReport:
    """The verdict for one piece of content."""

    findings: tuple[GuardrailFinding, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        """True if any finding is a hard BLOCK — this content cannot go to review as-is."""
        return any(f.severity is Severity.BLOCK for f in self.findings)

    @property
    def flagged(self) -> bool:
        """True if a human needs to look (any BLOCK or FLAG finding)."""
        return any(f.severity in (Severity.BLOCK, Severity.FLAG) for f in self.findings)

    @property
    def clean(self) -> bool:
        return not self.flagged

    def render(self) -> str:
        if not self.findings:
            return "guardrails: clean (no findings)"
        return "guardrails:\n" + "\n".join("  " + f.render() for f in self.findings)


@dataclass(frozen=True, slots=True)
class GuardrailRules:
    """The policy this guard enforces. Swap it for your brand to adapt the pipeline.

    Everything is plain data so the rules diff cleanly in review and can be loaded from a config
    file in a fuller build.
    """

    forbidden: tuple[str, ...] = ()
    claim_words: tuple[str, ...] = ()
    banned_tone: tuple[str, ...] = ()
    required_disclaimers: tuple[str, ...] = ()
    # If a regulated topic word appears, the matching disclaimer must be present.
    regulated_topics: tuple[str, ...] = ()


# A sensible, illustrative default policy. Replace for your brand (see module docstring).
DEFAULT_RULES = GuardrailRules(
    forbidden=(
        "guaranteed returns",
        "no risk",
        "miracle",
        "crushes the competition",
    ),
    claim_words=(
        "guaranteed",
        "100%",
        "risk-free",
        "cure",
        "#1",
        "best in the world",
        "instantly",
        "always",
        "never fails",
    ),
    banned_tone=(
        "!!!",
    ),
    required_disclaimers=(
        "Past performance does not guarantee future results.",
    ),
    regulated_topics=(
        "investment",
        "returns",
        "medical",
    ),
)

# A run of >= this many consecutive capital letters reads as shouting (ALL-CAPS tone marker).
_SHOUT_RE = re.compile(r"\b[A-Z]{5,}\b")


def _excerpt(text: str, needle: str, width: int = 28) -> str:
    """A small window of ``text`` around ``needle`` for the finding's evidence."""
    i = text.lower().find(needle.lower())
    if i < 0:
        return needle
    start = max(0, i - width // 2)
    end = min(len(text), i + len(needle) + width // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    return snippet


def _has_supporting_source(sources: Iterable[str]) -> bool:
    """A claim is allowed *if* the stage that wrote it cited a grounding source."""
    return any(bool(s) for s in sources)


def check_brand_compliance(
    text: str,
    *,
    rules: GuardrailRules = DEFAULT_RULES,
    sources: Iterable[str] = (),
) -> GuardrailReport:
    """Check one piece of content against the brand/compliance ``rules``.

    Parameters
    ----------
    text:
        The draft or variant to check.
    rules:
        The policy to enforce. Defaults to :data:`DEFAULT_RULES`; pass your own to adapt.
    sources:
        The grounding sources the content was built on (from the run's research/retrieval
        artifact). A superlative *claim* is downgraded from a hard flag to ``INFO`` when the
        content is grounded — an unsupported claim is the risky one.

    Returns
    -------
    GuardrailReport
        Structured findings. The pipeline routes a ``flagged`` report to a human and refuses to
        mark a ``blocked`` one review-ready.
    """
    findings: list[GuardrailFinding] = []
    low = text.lower()
    grounded = _has_supporting_source(sources)

    # 1) Forbidden language — hard block.
    for phrase in rules.forbidden:
        if phrase.lower() in low:
            findings.append(
                GuardrailFinding(
                    rule="forbidden-language",
                    severity=Severity.BLOCK,
                    message=f"contains banned phrase {phrase!r}",
                    excerpt=_excerpt(text, phrase),
                )
            )

    # 2) Unsubstantiated claims — flag unless grounded (then advisory).
    for word in rules.claim_words:
        if word.lower() in low:
            severity = Severity.INFO if grounded else Severity.FLAG
            note = (
                "claim present; grounded on a cited source — confirm the source supports it"
                if grounded
                else "absolute/superlative claim with no cited source — verify or remove"
            )
            findings.append(
                GuardrailFinding(
                    rule="unsupported-claim",
                    severity=severity,
                    message=f"{note} ({word!r})",
                    excerpt=_excerpt(text, word),
                )
            )

    # 3) Banned tone markers (explicit phrases + shouting).
    for marker in rules.banned_tone:
        if marker in text:
            findings.append(
                GuardrailFinding(
                    rule="tone",
                    severity=Severity.FLAG,
                    message=f"banned tone marker {marker!r}",
                    excerpt=_excerpt(text, marker),
                )
            )
    shout = _SHOUT_RE.search(text)
    if shout:
        findings.append(
            GuardrailFinding(
                rule="tone",
                severity=Severity.FLAG,
                message="ALL-CAPS shouting detected",
                excerpt=shout.group(0),
            )
        )

    # 4) Required disclaimers on regulated topics.
    touches_regulated = any(topic.lower() in low for topic in rules.regulated_topics)
    if touches_regulated:
        for disclaimer in rules.required_disclaimers:
            if disclaimer.lower() not in low:
                findings.append(
                    GuardrailFinding(
                        rule="missing-disclaimer",
                        severity=Severity.FLAG,
                        message=(
                            "regulated topic mentioned but required disclaimer is missing: "
                            f"{disclaimer!r}"
                        ),
                    )
                )

    return GuardrailReport(findings=tuple(findings))
