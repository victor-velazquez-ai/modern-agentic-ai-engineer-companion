#!/usr/bin/env python
"""Runnable demo — a brief becomes review-ready content, fully traced (MOCK by default).

This is the Appendix-G "Content production pipeline" use case end to end. It **composes** the
repo's pattern blueprints (it does not fork them):

  * ``rag-pipeline``        grounds every draft on the brand voice + product facts corpus,
  * ``agent-loop``          drives the draft + reflection/critique turns,
  * ``observability-stack`` wraps each stage in a span so the run is one auditable trace,
  * ``eval-harness``        scores the output for brand adherence + factual accuracy.

Run it::

    python demo.py                     # offline, deterministic, zero API spend (COMPANION_MOCK=1)
    COMPANION_MOCK=0 python demo.py     # live path: inject a gateway-backed model (keys required)

What it shows, in order:
  1. **ingest the corpus** — brand/guidelines.md -> a rag-pipeline retriever.
  2. **run a brief**       — brief -> research -> draft -> critique -> variants -> guardrails.
  3. **the artifacts**     — one typed, inspectable record per stage (provenance, not a blob).
  4. **the variants**      — one channel adaptation each (blog / email / social).
  5. **the guardrails**    — brand + compliance flags; a blocked piece never reaches review.
  6. **the trace + cost**  — the staged pipeline as a span tree; cost is $0.00 in MOCK mode.
  7. **review, not publish** — the run stops review-ready; a human is the approval gate.
  8. **a guardrail catch** — a deliberately off-brand draft is flagged/blocked, not shipped.
  9. **the evals**         — brand-adherence + factual-accuracy golden set (eval-harness).

Nothing here spends money by default; secrets (for the live path) come from the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the solution package importable when run straight from a clone (no install step).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.compose import ConsoleExporter, summarize  # noqa: E402  (after path wiring)
from pipeline.corpus import load_brand_context, load_briefs  # noqa: E402
from pipeline.guardrails import check_brand_compliance  # noqa: E402
from pipeline.stages import ContentPipeline, PipelineResult, Stage  # noqa: E402

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"
RULE = "=" * 78


def _h(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def show_run(result: PipelineResult) -> None:
    """Print the artifact ledger, the variants, the guardrail flags, and the trace."""
    run = result.run

    _h("2-4. Stage artifacts (one auditable record per stage)")
    for art in run.artifacts:
        print("  " + art.summary())

    _h("4. Channel variants (the review-ready drafts)")
    for channel, text in result.variants().items():
        print(f"\n--- {channel} ---\n{text}")

    _h("5. Guardrail report (brand + compliance)")
    guard = run.get(Stage.GUARDRAILS)
    reports = guard.content if guard else {}
    any_finding = False
    for channel, rep in reports.items():
        flag = "BLOCKED" if rep["blocked"] else ("flagged" if rep["flagged"] else "clean")
        print(f"  [{channel}] {flag}")
        for finding in rep["findings"]:
            any_finding = True
            print(f"      {finding}")
    if not any_finding:
        print("  (no findings — all variants are on-brand and grounded)")

    _h("6. Trace + cost (the staged pipeline as one span tree)")
    print(ConsoleExporter().export(result.tracer.trace))
    cost = summarize(result.tracer.trace)
    print(f"\n  total cost: ${cost.total_usd:.4f}" + ("   (MOCK — no spend)" if MOCK else ""))

    _h("7. Review gate")
    print(f"  review_ready = {run.review_ready}")
    print(f"  published    = {run.published}   <- always False: a human is the approval gate")


def demo_happy_path() -> None:
    """Run the first sample brief through the whole pipeline."""
    brand = load_brand_context()
    briefs = load_briefs()
    brief = briefs[0]

    _h(f"1. Loaded brand corpus + {len(briefs)} briefs — running brief '{brief.id}'")
    print(f"  topic    : {brief.topic}")
    print(f"  channels : {', '.join(brief.channels)}")
    print(f"  audience : {brief.audience}")

    pipeline = ContentPipeline(brand)
    result = pipeline.run(brief)
    show_run(result)


def demo_guardrail_catch() -> None:
    """Show the guardrails catching content that must never reach review as-is.

    These checks are deterministic and run on the *output*, so they are the same ones the
    pipeline applies to every variant — here we point them at a hand-written bad draft to make
    the catch visible.
    """
    _h("8. Guardrail catch (off-brand copy is flagged/blocked, not shipped)")
    bad = (
        "Our miracle dashboard delivers GUARANTEED returns with no risk!!! "
        "It is the #1 best in the world and works instantly, every time."
    )
    print(f"  draft: {bad}\n")
    report = check_brand_compliance(bad, sources=())  # no grounding -> claims are hard flags
    print(report.render())
    print(f"\n  blocked = {report.blocked}   (a blocked piece can't be marked review-ready)")


def demo_evals() -> None:
    """Run the brand-adherence + factual-accuracy golden set (eval-harness)."""
    _h("9. Brand-adherence + factual-accuracy evals (eval-harness)")
    # Import lazily so the demo still runs the pipeline even if the eval module is edited.
    from evals.run_evals import build_candidate, DATASET, PASS_THRESHOLD
    from pipeline.compose import Contains, LLMJudge, load_jsonl, run_grouped

    cases = load_jsonl(DATASET)
    candidate = build_candidate()
    graders = {"factual": Contains(), "brand": Contains(), "voice": LLMJudge()}
    report = run_grouped(candidate, cases, graders, default=Contains(), threshold=0.5)
    print(report.render())
    verdict = "PASS" if report.mean_score >= PASS_THRESHOLD else "REGRESSION"
    print(f"\n  [{verdict}] mean score {report.mean_score:.3f} (bar {PASS_THRESHOLD:.2f})")


def main() -> int:
    mode = "MOCK (offline, $0)" if MOCK else "LIVE (gateway-backed)"
    print(f"Content Production Pipeline — demo  [mode: {mode}]")
    demo_happy_path()
    demo_guardrail_catch()
    demo_evals()
    _h("Done — drafts are review-ready, nothing was published, no API spend in MOCK mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
