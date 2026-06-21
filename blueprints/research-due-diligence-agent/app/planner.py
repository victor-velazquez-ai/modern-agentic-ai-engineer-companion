"""Decompose a research question into sub-questions (composes ``multi-agent-supervisor``).

The first move of a due-diligence agent is the same as a human analyst's: break the big,
fuzzy question ("should we acquire Acme?") into a handful of *answerable* sub-questions
("what is the market size?", "who are the competitors?", "what are the risks?"). Each
sub-question is then handed to a retrieval/worker agent that gathers evidence for it.

Composition note
----------------
The supervisor/worker topology — *planner → workers → synthesizer* — lives in the
``multi-agent-supervisor`` pattern blueprint. We do **not** fork it. This module reuses its
:class:`~multi_agent_supervisor.SubTask` as the unit of delegated work and its
:class:`~multi_agent_supervisor.IterationGuard` as the planner's **step cap**, so a planner
can never emit an unbounded list of sub-questions (a runaway-loop guard from Ch 16).

The decomposition itself is deterministic (no model call) so the demo and the evals are
reproducible in MOCK mode. On the live path you would swap :func:`plan_questions` for a
model-driven planner that routes through ``llm-gateway`` — the rest of the pipeline is
unchanged because it only depends on the :class:`SubQuestion` surface below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from . import _compose  # noqa: F401 — side effect: puts sibling src/ on sys.path

# Imported from the sibling multi-agent-supervisor blueprint (NOT forked).
from multi_agent_supervisor import (  # type: ignore  # noqa: E402
    GuardTripped,
    IterationGuard,
    SubTask,
)

# A due-diligence question maps onto a standard set of *facets*. Each facet becomes a
# sub-question and carries the retrieval query terms a worker searches the corpus with.
# This is the domain knowledge the solution adds on top of the generic supervisor.
_FACETS: tuple[tuple[str, str, str], ...] = (
    # (facet id, the sub-question template, query terms for retrieval)
    ("overview", "What does {subject} do and what is its current scale?",
     "company overview product revenue customers headcount"),
    ("financials", "What are {subject}'s financials and unit economics?",
     "revenue ARR growth margin burn runway churn retention"),
    ("market", "How large is the market for {subject} and how fast is it growing?",
     "market size growth CAGR demand category"),
    ("competition", "Who competes with {subject} and how defensible is it?",
     "competitors competitive landscape differentiation moat"),
    ("customers", "What do {subject}'s customers and references say?",
     "customer sentiment references satisfaction complaints"),
    ("risks", "What are the key risks in {subject}?",
     "risk concentration security compliance regulatory"),
)

# Hard cap on how many sub-questions a single plan may contain. The IterationGuard enforces
# it; the default is generous for the six facets above but finite, so a future model-driven
# planner cannot fan out forever and bankrupt the run.
DEFAULT_MAX_SUBQUESTIONS = 8


@dataclass(frozen=True)
class SubQuestion:
    """One answerable sub-question the agent will gather evidence for.

    ``subtask`` is the underlying :class:`multi_agent_supervisor.SubTask`, so this plan can be
    fed straight into the supervisor topology. ``query`` is the retrieval query the worker
    uses against the corpus; keeping it separate from the human-readable ``text`` lets the
    sub-question read naturally while retrieval searches on dense keywords.
    """

    id: str
    text: str
    query: str
    subtask: SubTask

    @property
    def capability(self) -> str:
        return self.subtask.capability


# Capitalized words that commonly *start* a question but are not the subject. We skip these so
# "Should we acquire Acme Vector DB Inc.?" yields "Acme Vector DB Inc.", not "Should".
_LEADING_NONSUBJECT = frozenset(
    """should could would what when where which who why how is are do does can may might
    we i evaluate assess research analyze review the a an""".split()
)


def _subject_of(question: str) -> str:
    """Pull a plausible subject (a proper noun / capitalized phrase) out of the question.

    Prefers the first run of Capitalized words that is not a leading question/auxiliary word
    (so "Should we acquire Acme Vector DB" → "Acme Vector DB"). Falls back to a neutral
    "the target" so the sub-question templates always read cleanly. This is a cheap heuristic,
    not entity extraction — on the live path the planner model would name the subject directly.
    """
    for m in re.finditer(r"\b([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)", question):
        phrase = m.group(1).strip()
        first = phrase.split()[0].lower().strip(".")
        if first in _LEADING_NONSUBJECT:
            continue
        return phrase
    return "the target"


def plan_questions(
    question: str,
    *,
    facets: Sequence[tuple[str, str, str]] = _FACETS,
    max_subquestions: int = DEFAULT_MAX_SUBQUESTIONS,
) -> list[SubQuestion]:
    """Decompose ``question`` into bounded, retrievable sub-questions.

    Args:
        question: the top-level research / due-diligence question.
        facets: the (id, template, query-terms) triples to expand. Override to retarget the
            agent to a different question shape (see the README's "adapt it" section).
        max_subquestions: hard cap on the plan size, enforced by the supervisor's
            :class:`IterationGuard` — the planner's step cap.

    Returns:
        A list of :class:`SubQuestion`, each wrapping a ``multi_agent_supervisor.SubTask`` so
        the supervisor can route and fan it out.

    Raises:
        ValueError: if ``question`` is blank.
    """
    if not question or not question.strip():
        raise ValueError("research question must be non-empty")

    subject = _subject_of(question)
    guard = IterationGuard(max_iterations=max_subquestions)
    out: list[SubQuestion] = []
    for facet_id, template, query_terms in facets:
        try:
            guard.tick()  # bound the plan size — a runaway planner halts loudly
        except GuardTripped:
            break
        text = template.format(subject=subject)
        # The query the worker retrieves on: facet keywords plus the subject, so hybrid
        # search has both the rare proper noun and the topical terms to fuse on.
        query = f"{subject} {query_terms}"
        subtask = SubTask(
            id=f"q-{facet_id}",
            description=text,
            capability="research",
        )
        out.append(SubQuestion(id=facet_id, text=text, query=query, subtask=subtask))
    return out
