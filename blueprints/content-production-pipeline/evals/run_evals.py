#!/usr/bin/env python
"""Brand-adherence + factual-accuracy evals for the content pipeline (Ch 22).

This is the ``eval-harness`` blueprint pointed at *this* solution. The system under test (the
"candidate") is the pipeline itself: given a brief id, it runs the full brief -> research ->
draft -> critique -> variants -> guardrails flow and returns the on-brand **blog variant**. The
golden set (``brand_golden.jsonl``) then asserts two things that matter for content:

* **factual accuracy** — the output surfaces a *grounded* product fact (it can't, by
  construction, fabricate one — the MOCK draft writes only from retrieved snippets); and
* **brand adherence** — the output keeps the on-brand qualifier ("results vary") and does not
  sell a roadmap-only feature as shipping.

Tags route the grader (``run_grouped`` picks the first matching tag):
  ``factual`` / ``brand`` -> :class:`~eval_harness.graders.deterministic.Contains`
  ``voice``               -> :class:`~eval_harness.graders.llm_judge.LLMJudge` (mock judge)

Free and offline by default (``COMPANION_MOCK=1``). The LLM-judge uses the harness's
deterministic mock judge unless you opt into spend; nothing here calls an API by default.

Run it::

    python evals/run_evals.py            # prints the report; exits non-zero if it regresses
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the solution package importable when run as a script (study & adapt, not a wheel).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.compose import (  # noqa: E402  (after the path wiring above)
    Contains,
    LLMJudge,
    load_jsonl,
    run_grouped,
)
from pipeline.corpus import briefs_by_id, load_brand_context  # noqa: E402
from pipeline.stages import ContentPipeline  # noqa: E402

DATASET = Path(__file__).resolve().parent / "brand_golden.jsonl"

# A run is healthy when the mean score clears this bar. The brand/factual checks are
# deterministic in MOCK mode, so this is a real regression gate, not a flaky threshold.
PASS_THRESHOLD = 0.8


def build_candidate():
    """Build the `(brief_id) -> blog-variant text` candidate the graders score.

    Indexing the brand corpus once (outside the closure) keeps the eval fast: every case reuses
    the same ``rag-pipeline`` retriever, exactly as a real run would.
    """
    brand = load_brand_context()
    briefs = briefs_by_id()
    pipeline = ContentPipeline(brand)

    def candidate(brief_id: str) -> str:
        brief = briefs[str(brief_id)]
        result = pipeline.run(brief)
        variants = result.variants()
        # Grade the blog variant (the long-form, fact-dense one); fall back to any variant.
        return variants.get("blog") or next(iter(variants.values()), "")

    return candidate


def main() -> int:
    cases = load_jsonl(DATASET)
    candidate = build_candidate()

    # Route by tag: deterministic substring checks for facts/brand, the (mock) judge for voice.
    graders = {
        "factual": Contains(),   # needle defaults to the case's `expected`
        "brand": Contains(),
        "voice": LLMJudge(),     # mock judge in MOCK mode — free + deterministic
    }
    report = run_grouped(
        candidate, cases, graders, default=Contains(), threshold=0.5
    )

    print(report.render())
    print()
    ok = report.mean_score >= PASS_THRESHOLD
    verdict = "PASS" if ok else "REGRESSION"
    print(f"[{verdict}] mean score {report.mean_score:.3f} (bar {PASS_THRESHOLD:.2f})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
