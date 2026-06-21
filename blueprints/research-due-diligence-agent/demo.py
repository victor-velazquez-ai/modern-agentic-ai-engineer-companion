#!/usr/bin/env python3
"""MOCK-mode demo: a research question in, a cited brief (with verification) out.

Run it::

    python demo.py
    python demo.py "Should we acquire Acme Vector DB Inc.?"

What it shows
-------------
* a question is **decomposed** into bounded sub-questions (``planner`` → multi-agent-supervisor);
* retrieval workers **fan out** over the corpus and gather *cited* evidence
  (``workers`` → rag-pipeline + the agent-loop tool seam);
* the evidence is **synthesized** into a brief where *every claim links to a source*;
* a **reflection pass** verifies each claim against its source and **flags** any that is uncited
  or unsupported;
* the run is **traced** with step/cost caps (observability-stack) and costs **$0** in MOCK.

No API key and no spend by default: ``COMPANION_MOCK`` defaults to ``1``. Set
``COMPANION_MOCK=0`` (and ``ANTHROPIC_API_KEY``) only if you wire in the live model path.

To prove the uncited-claim guard is real, this script also injects one *uncited* claim into a
copy of the brief and shows the reflection pass catching it.
"""

from __future__ import annotations

import os
import sys

# Default to MOCK so a bare `python demo.py` never spends. Set before importing the package.
os.environ.setdefault("COMPANION_MOCK", "1")

# Make `from app import ...` work whether run from the blueprint dir or elsewhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import build_agent  # noqa: E402
from app.reflect import reflect  # noqa: E402
from app.synthesize import BriefSection, CitedBrief, CitedClaim  # noqa: E402

DEFAULT_QUESTION = "Should we acquire Acme Vector DB Inc.?"


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main(argv: list[str]) -> int:
    question = argv[1] if len(argv) > 1 else DEFAULT_QUESTION
    mock = os.environ.get("COMPANION_MOCK", "1") not in {"0", "false", "no"}

    _banner("Research & Due-Diligence Agent — MOCK demo" if mock else "LIVE mode")
    print(f"Question: {question}")
    print(f"Mode    : {'MOCK (offline, $0, deterministic)' if mock else 'LIVE (billed)'}")

    # Build the composed agent over the committed sample corpus and run it.
    agent = build_agent()
    report = agent.run(question)

    _banner("Cited brief + verification")
    print(report.render())

    # --- prove the guard: an uncited claim must be flagged -----------------------
    _banner("Guard check: an uncited claim is flagged")
    tampered = CitedBrief(
        question=report.brief.question,
        sections=report.brief.sections
        + (
            BriefSection(
                facet="injected",
                heading="Injected (uncited) claim",
                claims=(
                    CitedClaim(
                        text="Acme will definitely triple its revenue next year.",
                        citations=(),  # <-- no source: this MUST be flagged
                        facet="injected",
                    ),
                ),
            ),
        ),
        sources=report.brief.sources,
    )
    tampered_reflection = reflect(tampered, list(report.evidence))
    flagged = tampered_reflection.flagged
    print(f"flagged claims: {len(flagged)} (expected >= 1)")
    for c in flagged:
        print(f"  ! [{c.status}] {c.text[:64]}  — {c.reason}")

    # Exit non-zero if the guard failed to catch the injected uncited claim — makes the demo
    # usable as a smoke test in CI.
    ok = any(c.status == "uncited" for c in flagged)
    _banner("Result")
    print("PASS: uncited claim was flagged." if ok else "FAIL: uncited claim slipped through!")
    print(
        f"Brief faithfulness (clean run): {report.faithfulness:.0%} "
        f"of {report.reflection.total} claims grounded."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
