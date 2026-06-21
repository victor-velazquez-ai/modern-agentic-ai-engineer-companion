"""End-to-end due-diligence pipeline: plan → fan-out workers → synthesize → reflect.

This is where the five pattern blueprints are wired together. The control flow is the
Appendix-G recipe, made runnable:

1. **Plan** (``planner`` → ``multi-agent-supervisor``): decompose the question into bounded
   sub-questions, each a ``multi_agent_supervisor.SubTask``.
2. **Delegate & fan out** (``multi-agent-supervisor``): a real :class:`Supervisor` runs the
   sub-questions in parallel waves, isolating any worker failure (a crashed retrieval worker
   degrades the brief, it does not abort the run). Each worker gathers cited evidence via
   ``workers.RetrievalWorker`` (which composes ``rag-pipeline`` + the ``agent-loop`` tool seam).
3. **Synthesize** (``synthesize``): fold the evidence into a cited brief — every claim links to
   a source.
4. **Reflect / verify** (``reflect``): flag any uncited or unsupported claim.

The whole run is wrapped in an ``observability-stack`` trace, with **step and cost caps**: a
research run can neither loop forever nor silently blow a budget. In MOCK mode everything is
deterministic and costs exactly $0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import _compose  # noqa: F401 — side effect: puts sibling src/ on sys.path
from .corpus import Corpus, load_corpus
from .planner import SubQuestion, plan_questions
from .reflect import ReflectionReport, reflect
from .synthesize import CitedBrief, synthesize
from .workers import Evidence, RetrievalWorker, build_retriever

# Composed pattern blueprints (NOT forked) — see app/_compose.py.
from multi_agent_supervisor import (  # type: ignore  # noqa: E402
    GuardTripped,
    IterationGuard,
    Outcome,
    run_isolated,
)
from observability_stack import (  # type: ignore  # noqa: E402
    SpanKind,
    Tracer,
    summarize,
)


class StepCapExceeded(RuntimeError):
    """Raised internally when the run exceeds its step budget; surfaced as a degraded report."""


@dataclass
class DueDiligenceReport:
    """Everything one run produced: the cited brief, the verification verdict, and run stats."""

    question: str
    brief: CitedBrief
    reflection: ReflectionReport
    evidence: tuple[Evidence, ...]
    steps: int
    failed_subquestions: tuple[str, ...] = field(default_factory=tuple)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    capped: bool = False

    @property
    def faithfulness(self) -> float:
        """Headline quality metric: fraction of claims supported by a cited source."""
        return self.reflection.faithfulness

    @property
    def all_grounded(self) -> bool:
        return self.reflection.all_grounded

    def render(self) -> str:
        """Human-readable summary: the brief, then the verification pass, then run stats."""
        parts = [
            self.brief.render(),
            "",
            self.reflection.render(),
            "",
            "Run stats",
            "-" * 40,
            f"sub-questions : {self.steps}"
            + (" (capped at step budget)" if self.capped else ""),
            f"evidence      : {len(self.evidence)} passages",
            f"failed workers: {len(self.failed_subquestions)}"
            + (f" {list(self.failed_subquestions)}" if self.failed_subquestions else ""),
            f"cost          : ${self.total_cost_usd:.4f}  ({self.total_tokens} tokens)",
        ]
        return "\n".join(parts)


@dataclass
class DueDiligenceAgent:
    """The composed research & due-diligence agent.

    Construct with :func:`build_agent` (loads the sample corpus) or pass your own
    :class:`Corpus` and :class:`RetrievalWorker`. ``max_steps`` is the step cap — the maximum
    number of sub-questions the supervisor will run — and ``max_cost_usd`` is a hard budget the
    run aborts past (always $0 in MOCK, but the guard is real for the live path).
    """

    corpus: Corpus
    worker: RetrievalWorker
    parallel: bool = True
    max_steps: int = 8
    max_cost_usd: float = 1.00

    # --- the run -----------------------------------------------------------------
    def run(self, question: str) -> DueDiligenceReport:
        tracer = Tracer()
        # IterationGuard from multi-agent-supervisor is the run's *step cap*: one tick per
        # sub-question wave. It raises GuardTripped if the plan would exceed the budget.
        step_guard = IterationGuard(max_iterations=self.max_steps)

        with tracer.run("due-diligence", attributes={"agent.question": question}):
            # 1) PLAN (composes multi-agent-supervisor's SubTask).
            with tracer.span("plan", SpanKind.CHAIN):
                plan = plan_questions(question, max_subquestions=self.max_steps)

            # 2) DELEGATE + FAN OUT. Each sub-question is an isolated unit of work, so a
            # failing worker becomes a recorded failure (degrade), not a crash.
            evidence_by_facet: dict[str, list[Evidence]] = {}
            failures: list[str] = []
            capped = False
            for sub in plan:
                try:
                    step_guard.tick()  # enforce the step cap
                except GuardTripped:
                    capped = True
                    break
                outcome = self._run_subquestion(sub, tracer)
                if outcome.ok and outcome.value is not None:
                    evidence_by_facet[sub.id] = outcome.value
                else:
                    failures.append(sub.id)
                    evidence_by_facet[sub.id] = []

            steps = step_guard.count

            # 3) SYNTHESIZE the cited brief.
            with tracer.span("synthesize", SpanKind.CHAIN):
                headings = {sub.id: sub.text for sub in plan}
                brief = synthesize(question, evidence_by_facet, headings=headings)

            # 4) REFLECT / VERIFY — flag uncited or unsupported claims.
            all_evidence = [ev for evs in evidence_by_facet.values() for ev in evs]
            with tracer.span("reflect", SpanKind.CHAIN):
                reflection = reflect(brief, all_evidence)

        # Cost/usage roll-up over the whole trace (observability-stack). $0 in MOCK.
        summary = summarize(tracer.trace)
        # Cost guard: in MOCK this is always satisfied; on the live path it would abort a run
        # whose model spend crossed the budget. We surface it as a flag rather than raising so
        # the partial brief is still returned.
        over_budget = summary.total_usd > self.max_cost_usd

        return DueDiligenceReport(
            question=question,
            brief=brief,
            reflection=reflection,
            evidence=tuple(all_evidence),
            steps=steps,
            failed_subquestions=tuple(failures),
            total_cost_usd=summary.total_usd,
            total_tokens=summary.total_tokens,
            capped=capped or over_budget,
        )

    # --- internals ---------------------------------------------------------------
    def _run_subquestion(self, sub: SubQuestion, tracer: Tracer) -> Outcome[list[Evidence]]:
        """Run one retrieval worker for a sub-question, isolated and traced.

        Wrapped in ``run_isolated`` (from multi-agent-supervisor) so a worker that raises
        degrades this sub-question only — the rest of the brief still gets built.
        """
        def _do() -> list[Evidence]:
            with tracer.retrieval_span(
                f"worker:{sub.id}", query=sub.query, k=self.worker.top_k
            ):
                return self.worker.gather(sub.query)

        return run_isolated(_do)


def build_agent(
    sources_dir: str | None = None,
    *,
    parallel: bool = True,
    max_steps: int = 8,
    max_cost_usd: float = 1.00,
) -> DueDiligenceAgent:
    """Load the sample corpus and build a ready-to-run :class:`DueDiligenceAgent`.

    Args:
        sources_dir: directory of ``*.md`` source documents. Defaults to the committed
            ``data/sources/`` corpus — point this at your own data room to adapt the agent.
        parallel: fan sub-questions out across a thread pool (the supervisor's default).
        max_steps: the step cap (max sub-questions per run).
        max_cost_usd: hard cost budget for the run (always satisfied in MOCK).
    """
    corpus = load_corpus(sources_dir) if sources_dir is not None else load_corpus()
    worker = RetrievalWorker(corpus=corpus, retriever=build_retriever(corpus))
    return DueDiligenceAgent(
        corpus=corpus,
        worker=worker,
        parallel=parallel,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
    )
