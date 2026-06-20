"""Input / output guards (Ch 41) — PII, injection, content safety.

Two questions Ch 41 makes you answer before a model call ships:

* **Input guards** run on the prompt *before* it reaches the provider. They block
  obvious prompt-injection ("ignore previous instructions and …") and can redact
  PII so secrets never leave your perimeter.
* **Output guards** run on the model's text *before* it reaches the user. They
  redact PII the model may have echoed and flag unsafe content.

These are *defaults you can enforce*, not a complete safety system — the regexes
here are deliberately simple and readable. The value is the **seam**: one place
every call passes through, so the policy is consistent and testable. Swap the
detectors for a real classifier/DLP service without touching callers.

Guards fail **closed** for blocks (a blocked input raises) and **safe** for
redaction (unknown → leave alone), which is the conservative default Ch 41 argues
for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Pattern


class GuardAction(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass(frozen=True)
class GuardFinding:
    """One thing a guard noticed."""

    category: str
    action: GuardAction
    detail: str = ""


@dataclass
class GuardResult:
    """Outcome of running a guard over some text."""

    text: str
    findings: list[GuardFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.action is GuardAction.BLOCK for f in self.findings)

    @property
    def redacted(self) -> bool:
        return any(f.action is GuardAction.REDACT for f in self.findings)


class GuardrailError(RuntimeError):
    """Raised when an input is blocked outright (fail-closed)."""

    def __init__(self, result: GuardResult) -> None:
        cats = ", ".join(f.category for f in result.findings if f.action is GuardAction.BLOCK)
        super().__init__(f"blocked by guardrail: {cats}")
        self.result = result


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

# PII patterns → replacement token. Order matters (email before generic digits).
_PII_PATTERNS: list[tuple[str, Pattern[str], str]] = [
    ("email", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (
        "credit_card",
        re.compile(r"\b(?:\d[ -]?){13,16}\b"),
        "[REDACTED_CC]",
    ),
    (
        "ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    (
        "phone",
        re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b"),
        "[REDACTED_PHONE]",
    ),
    (
        "api_key",
        # Provider key prefixes (sk-, sk-ant-, pk-, ghp_, xoxb-) followed by a
        # long token that may itself contain one internal '-' or '_' separator.
        re.compile(r"\b(?:sk|pk|ghp|xoxb)[-_](?:[A-Za-z0-9]+[-_])?[A-Za-z0-9]{16,}\b"),
        "[REDACTED_KEY]",
    ),
]

# Prompt-injection / jailbreak phrasings. Conservative, high-precision set.
_INJECTION_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("injection", re.compile(r"ignore (?:all |the )?(?:previous|prior|above) instructions", re.I)),
    ("injection", re.compile(r"disregard (?:all |the )?(?:previous|prior|above)", re.I)),
    ("injection", re.compile(r"you are now (?:in )?(?:dan|developer|jailbreak) mode", re.I)),
    ("injection", re.compile(r"reveal (?:your )?(?:system prompt|instructions)", re.I)),
    ("injection", re.compile(r"\bprint (?:your )?(?:system prompt|secret)", re.I)),
]

# Unsafe-content cues. A stand-in for a real safety classifier.
_UNSAFE_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("self_harm", re.compile(r"\bhow to (?:kill|harm) (?:myself|yourself)\b", re.I)),
    ("weapons", re.compile(r"\b(?:build|make) a (?:bomb|bioweapon)\b", re.I)),
]


def redact_pii(text: str) -> tuple[str, list[GuardFinding]]:
    """Replace recognised PII with redaction tokens. Fails safe (leaves unknown)."""

    findings: list[GuardFinding] = []
    out = text
    for category, pattern, token in _PII_PATTERNS:
        new, n = pattern.subn(token, out)
        if n:
            findings.append(
                GuardFinding(category, GuardAction.REDACT, f"{n} match(es)")
            )
            out = new
    return out, findings


def detect_injection(text: str) -> list[GuardFinding]:
    findings: list[GuardFinding] = []
    for category, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append(GuardFinding(category, GuardAction.BLOCK, pattern.pattern))
    return findings


def detect_unsafe(text: str) -> list[GuardFinding]:
    findings: list[GuardFinding] = []
    for category, pattern in _UNSAFE_PATTERNS:
        if pattern.search(text):
            findings.append(GuardFinding(category, GuardAction.BLOCK, pattern.pattern))
    return findings


# ---------------------------------------------------------------------------
# Guard policy
# ---------------------------------------------------------------------------


@dataclass
class GuardConfig:
    block_injection: bool = True
    block_unsafe: bool = True
    redact_pii_input: bool = True
    redact_pii_output: bool = True


class Guard:
    """Runs the configured detectors over input and output text."""

    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def check_input(self, text: str) -> GuardResult:
        """Inspect a prompt. Redacts PII; flags injection/unsafe as BLOCK."""

        findings: list[GuardFinding] = []
        out = text
        if self.config.block_injection:
            findings.extend(detect_injection(text))
        if self.config.block_unsafe:
            findings.extend(detect_unsafe(text))
        if self.config.redact_pii_input:
            out, pii = redact_pii(out)
            findings.extend(pii)
        return GuardResult(text=out, findings=findings)

    def check_output(self, text: str) -> GuardResult:
        """Inspect model output before returning it. Redacts leaked PII."""

        findings: list[GuardFinding] = []
        out = text
        if self.config.redact_pii_output:
            out, pii = redact_pii(out)
            findings.extend(pii)
        if self.config.block_unsafe:
            findings.extend(detect_unsafe(text))
        return GuardResult(text=out, findings=findings)

    def enforce_input(self, text: str) -> str:
        """Convenience: redact-and-return, or raise :class:`GuardrailError` on block."""

        result = self.check_input(text)
        if result.blocked:
            raise GuardrailError(result)
        return result.text


__all__ = [
    "Guard",
    "GuardConfig",
    "GuardResult",
    "GuardFinding",
    "GuardAction",
    "GuardrailError",
    "redact_pii",
    "detect_injection",
    "detect_unsafe",
]
