"""screen — the orchestrator that wires the four pattern blueprints into one pass.

This is the *composition* itself: a single :class:`Screener` that, per monitored item, runs the
pipeline the PLAN describes —

    retrieve policy rule  (rag-pipeline, via policy_check)
        -> classify clear/flag with structured output  (agent-loop, via classify)
        -> add an anomaly signal on transactions        (statistical, via anomaly)
        -> route flags to the human queue               (HITL, via route)
        -> write an append-only audit record            (audit/ledger)

— all inside one ``observability-stack`` run trace. Keeping the screening logic here (not in
``demo.py``) means the **same code path** is what the eval-harness scores: the demo and the evals
call :meth:`Screener.screen` / :func:`classify_label`, so "what we measured" and "what we ship"
can't drift.

Every dependency is injected or defaulted to its offline mock, so the whole pass runs free and
deterministically under ``COMPANION_MOCK=1``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import add_blueprint_paths
from .anomaly import AmountAnomalyDetector, AnomalySignal
from .classify import Assessment, Classifier
from .policy_check import PolicyIndex, PolicyMatch
from .route import AdjudicationQueue, ReviewTicket

add_blueprint_paths()

from observability_stack import SpanKind, Tracer  # noqa: E402  (path wired above)


@dataclass
class ScreenResult:
    """The outcome of screening one item: its verdict, the rule basis, and any routing/anomaly."""

    item_id: str
    item_text: str
    match: PolicyMatch
    assessment: Assessment
    anomaly: AnomalySignal | None
    ticket: ReviewTicket | None  # a review ticket iff the item was flagged

    @property
    def flagged(self) -> bool:
        return self.assessment.flagged


class Screener:
    """Composes the four pattern blueprints into a compliance screening pass.

    Build it once (``Screener.build()`` wires the policy index, classifier, queue, ledger, and a
    tracer); call :meth:`screen` per item or :meth:`screen_stream` over a batch. The screener
    *flags and routes*; it never adjudicates — that is the human's job on the queue.
    """

    def __init__(
        self,
        *,
        policy_index: PolicyIndex,
        classifier: Classifier,
        queue: AdjudicationQueue,
        ledger: Any,  # audit.ledger.AuditLedger — typed Any to avoid importing across the seam
        anomaly_detector: AmountAnomalyDetector,
        tracer: Tracer | None = None,
    ) -> None:
        self.policy_index = policy_index
        self.classifier = classifier
        self.queue = queue
        self.ledger = ledger
        self.anomaly_detector = anomaly_detector
        self.tracer = tracer or Tracer(run_id="compliance-screen")

    @classmethod
    def build(cls, *, ledger: Any, classifier: Classifier | None = None) -> "Screener":
        """Construct a screener with the standard composition (policy index from the corpus)."""
        return cls(
            policy_index=PolicyIndex.from_corpus(),
            classifier=classifier or Classifier(),
            queue=AdjudicationQueue(),
            ledger=ledger,
            anomaly_detector=AmountAnomalyDetector(),
        )

    def fit_anomaly(self, amounts: list[float]) -> None:
        """Fit the anomaly detector on the population of transaction amounts in the batch."""
        self.anomaly_detector.fit(amounts)

    def screen(
        self, *, item_id: str, text: str, amount: float | None = None
    ) -> ScreenResult:
        """Screen one item end to end, tracing each stage and writing one audit record.

        Stages, each its own span so the trace reads like the pipeline:
          retrieval -> classification -> (anomaly) -> routing -> audit.
        """
        with self.tracer.span(f"screen:{item_id}", SpanKind.CHAIN):
            # 1) rag-pipeline: ground the item in the most relevant policy rule.
            with self.tracer.retrieval_span(query=text, k=4):
                match = self.policy_index.most_relevant_rule(text)

            # 2) agent-loop: structured, confidence-bearing clear/flag decision.
            with self.tracer.model_span(
                "classify",
                model="mock-model",
                input_tokens=0,
                output_tokens=0,
                attributes={"rule_id": match.rule_id},
            ):
                assessment = self.classifier.assess(text, match)

            # 3) statistical anomaly signal (transactions only) — raises a second reason to look.
            anomaly = self.anomaly_detector.check(amount) if amount is not None else None

            # 4) route: flags become human-review tickets; clears pass through.
            ticket: ReviewTicket | None = None
            routed_to = "none"
            if assessment.flagged:
                ticket = self.queue.enqueue(
                    item_id=item_id,
                    item_text=text,
                    assessment=assessment,
                    rule_title=match.title,
                    basis=match.snippet,
                )
                routed_to = "human-review-queue"

            # 5) audit: append-only, hash-chained record of the decision + its basis.
            self.ledger.append(
                item_id=item_id,
                decision=assessment.label,
                rule_id=assessment.rule_id,
                rule_title=match.title if assessment.flagged else "",
                confidence=assessment.confidence,
                basis=(match.snippet if assessment.flagged else assessment.reason),
                routed_to=routed_to,
                anomaly=(anomaly.reason if anomaly else ""),
            )

        return ScreenResult(
            item_id=item_id,
            item_text=text,
            match=match,
            assessment=assessment,
            anomaly=anomaly,
            ticket=ticket,
        )

    def screen_stream(self, items: list[dict[str, Any]]) -> list[ScreenResult]:
        """Screen a batch of items (dicts with ``id``/``text``/optional ``amount``).

        Fits the anomaly detector on the batch's amounts first (so "outlier" is relative to *this*
        population), then screens each item in order under one run trace.
        """
        amounts = [float(i["amount"]) for i in items if i.get("amount") is not None]
        self.fit_anomaly(amounts)
        results: list[ScreenResult] = []
        with self.tracer.run("compliance-monitoring-run"):
            for item in items:
                results.append(
                    self.screen(
                        item_id=str(item["id"]),
                        text=str(item["text"]),
                        amount=item.get("amount"),
                    )
                )
        return results


# --- the eval candidate: one function, the exact path the golden set scores --------------------

_SHARED_INDEX: PolicyIndex | None = None


def classify_label(text: str) -> str:
    """Screen one piece of text and return just its label ("clear" | "flag").

    This is the candidate the eval-harness runs over ``evals/flags_golden.jsonl``: it exercises the
    real retrieve -> classify path (no audit/routing side effects), so the evals measure the same
    decision logic the demo ships. The policy index is built once and cached for the whole run.
    """
    global _SHARED_INDEX
    if _SHARED_INDEX is None:
        _SHARED_INDEX = PolicyIndex.from_corpus()
    match = _SHARED_INDEX.most_relevant_rule(text)
    assessment = Classifier().assess(text, match)
    return assessment.label
