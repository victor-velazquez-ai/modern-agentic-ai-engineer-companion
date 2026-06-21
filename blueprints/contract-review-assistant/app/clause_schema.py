"""The validated clause / term model (Ch 15 — Structured Outputs).

A contract review is only as trustworthy as its *structure*. Free-text "the agent noticed a
liability clause" is unusable in a legal workflow; a typed, validated ``Clause`` — clause type,
the verbatim span, where it sits in the document, and a normalized value — is what a lawyer can
filter, sort, redline, and (critically) **audit**. This module is the schema and a dependency-
free validator/extractor for it.

Two deliberate choices, both straight from Ch 15:

* **A closed vocabulary of clause types.** :class:`ClauseType` is an ``Enum`` so an extractor
  cannot invent a category. Unknown text becomes :attr:`ClauseType.OTHER`, never a silent new
  label that the playbook has no rule for.
* **Validation is structural, not semantic.** :func:`validate_clause` checks that the shape is
  right (non-empty type/text, span present in the source, etc.). Whether the *content* is risky
  is the playbook's job (``flags.py``) — separation of concerns the book insists on.

The extractor here (:func:`extract_clauses`) is a deterministic, offline heading/keyword
splitter — the MOCK stand-in for a real structured-output model call (which, on the live path,
would route through ``llm-gateway`` and return JSON validated against this same schema). It
spends nothing and is reproducible, so the demo and evals run for free.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ClauseType(str, Enum):
    """The closed set of clause categories this assistant understands.

    Closed on purpose (Ch 15): every flag downstream is keyed by a clause type, and a playbook
    rule exists per type. A model that could emit an arbitrary string would route real risk into
    a bucket no rule covers. Anything unrecognized lands in :attr:`OTHER` and is reported as
    *unclassified* rather than dropped.
    """

    LIABILITY = "liability"
    INDEMNIFICATION = "indemnification"
    TERMINATION = "termination"
    CONFIDENTIALITY = "confidentiality"
    PAYMENT_TERMS = "payment_terms"
    GOVERNING_LAW = "governing_law"
    WARRANTY = "warranty"
    IP_OWNERSHIP = "ip_ownership"
    DATA_PROTECTION = "data_protection"
    OTHER = "other"

    def __str__(self) -> str:  # so f-strings render "liability", not "ClauseType.LIABILITY"
        return self.value


@dataclass(frozen=True, slots=True)
class Clause:
    """One extracted clause: its type, the verbatim text, and provenance.

    Attributes
    ----------
    id:
        Stable, document-scoped identifier (``{doc_id}::{index}``) so a clause keeps its
        identity across re-extraction — the same property the rag chunk ids have.
    clause_type:
        One :class:`ClauseType`.
    heading:
        The section heading the clause was found under (``""`` if none) — useful context for
        the reviewer and for citing the location.
    text:
        The verbatim clause text. This is what a redline edits and what a flag must cite — never
        a paraphrase.
    doc_id:
        Which contract this came from.
    index:
        0-based position of the clause within its document.
    """

    id: str
    clause_type: ClauseType
    heading: str
    text: str
    doc_id: str
    index: int

    @property
    def location(self) -> str:
        """A human/citation-friendly locator, e.g. ``contract-acme::3 (§ Limitation of Liability)``."""
        section = f" (§ {self.heading})" if self.heading else ""
        return f"{self.id}{section}"


class ClauseValidationError(ValueError):
    """Raised when an extracted clause violates the structural contract."""


def validate_clause(clause: Clause, *, source_text: str | None = None) -> Clause:
    """Structurally validate one clause; return it unchanged or raise.

    Checks (shape, not meaning):

    * ``id`` and ``text`` are non-empty;
    * ``clause_type`` is a real :class:`ClauseType`;
    * ``index`` is non-negative;
    * if ``source_text`` is supplied, the clause ``text`` actually occurs in it — the guard that
      stops a model from "citing" a span it hallucinated (an *uncited* clause is a failure mode
      the PLAN calls out explicitly).
    """
    if not clause.id:
        raise ClauseValidationError("clause.id must be non-empty")
    if not clause.text.strip():
        raise ClauseValidationError(f"clause {clause.id!r} has empty text")
    if not isinstance(clause.clause_type, ClauseType):
        raise ClauseValidationError(f"clause {clause.id!r} has non-enum clause_type")
    if clause.index < 0:
        raise ClauseValidationError(f"clause {clause.id!r} has negative index")
    if source_text is not None and clause.text not in source_text:
        raise ClauseValidationError(
            f"clause {clause.id!r} text is not a verbatim span of its source document "
            "(possible hallucinated citation)"
        )
    return clause


# --- the offline (MOCK) extractor --------------------------------------------------------

# Keyword cues that map a section's text/heading onto a ClauseType. Order matters only for ties;
# the first cue that matches wins. This is the deterministic stand-in for a structured-output
# model: cheap, explainable, good enough to drive the demo and evals with zero spend.
_TYPE_CUES: tuple[tuple[ClauseType, tuple[str, ...]], ...] = (
    (ClauseType.LIABILITY, ("limitation of liability", "liable", "liability", "damages")),
    (ClauseType.INDEMNIFICATION, ("indemnif", "hold harmless", "defend")),
    (ClauseType.TERMINATION, ("termination", "terminate", "notice period")),
    (ClauseType.CONFIDENTIALITY, ("confidential", "non-disclosure", "nda")),
    (ClauseType.PAYMENT_TERMS, ("payment", "net 30", "net 60", "net 90", "invoice", "fees")),
    (ClauseType.GOVERNING_LAW, ("governing law", "jurisdiction", "venue", "governed by")),
    (ClauseType.WARRANTY, ("warrant", "as is", "fitness for a particular purpose")),
    (ClauseType.IP_OWNERSHIP, ("intellectual property", "ownership of", "work product", "ip ")),
    (ClauseType.DATA_PROTECTION, ("data protection", "personal data", "gdpr", "processing of data")),
)

# Section headings look like "1. Limitation of Liability" or "SECTION 5 — Termination" on their
# own line. We split the contract on these so each clause is a (heading, body) unit.
_HEADING_RE = re.compile(
    r"^\s*(?:section\s+)?\d+[.)]?\s*[-–—]?\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def classify(text: str, heading: str = "") -> ClauseType:
    """Pick the best :class:`ClauseType` for a clause body + heading (offline heuristic)."""
    haystack = f"{heading}\n{text}".lower()
    for clause_type, cues in _TYPE_CUES:
        if any(cue in haystack for cue in cues):
            return clause_type
    return ClauseType.OTHER


def extract_clauses(doc_id: str, contract_text: str) -> list[Clause]:
    """Split a contract into validated :class:`Clause` objects (deterministic, offline).

    Strategy: find numbered/section headings, treat the text between consecutive headings as one
    clause body, classify it, and validate that the captured span is verbatim. A contract with no
    recognizable headings degrades to a single ``OTHER`` clause holding the whole text, so nothing
    is silently dropped.

    This is the MOCK realization of a Ch 15 structured-output extraction; the live path swaps in a
    model call (via ``llm-gateway``) that returns JSON validated against this very schema.
    """
    headings = list(_HEADING_RE.finditer(contract_text))
    clauses: list[Clause] = []

    if not headings:
        body = contract_text.strip()
        if body:
            clauses.append(
                validate_clause(
                    Clause(
                        id=f"{doc_id}::0",
                        clause_type=classify(body),
                        heading="",
                        text=body,
                        doc_id=doc_id,
                        index=0,
                    ),
                    source_text=contract_text,
                )
            )
        return clauses

    index = 0
    for i, match in enumerate(headings):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(contract_text)
        body = contract_text[body_start:body_end].strip()
        if not body:
            continue
        clauses.append(
            validate_clause(
                Clause(
                    id=f"{doc_id}::{index}",
                    clause_type=classify(body, heading),
                    heading=heading,
                    text=body,
                    doc_id=doc_id,
                    index=index,
                ),
                source_text=contract_text,
            )
        )
        index += 1
    return clauses


def clause_types(clauses: Iterable[Clause]) -> list[ClauseType]:
    """The distinct clause types present (sorted by value) — for coverage reporting."""
    return sorted({c.clause_type for c in clauses}, key=str)
