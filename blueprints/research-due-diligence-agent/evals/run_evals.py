#!/usr/bin/env python3
"""Citation-faithfulness + coverage evals (composes ``eval-harness``).

Two qualities make or break a due-diligence agent, and both are checked here against a golden
set (``faithfulness_golden.jsonl``):

* **Coverage** — for a given sub-question, did retrieval surface the source that actually
  contains the answer? A brief that never retrieves the risk memo cannot mention the risk.
* **Faithfulness** — is every claim in the synthesized brief grounded in a cited source? An
  uncited or unsupported claim is a failure (the reflection pass is what we are scoring).

Both are graded with the ``eval-harness`` pattern blueprint — its :class:`Case`, :class:`Contains`
grader, and :func:`run` — which we **import, not fork** (see ``app/_compose.py``). The harness
also gives a non-zero exit on regression, so this doubles as a CI gate.

Run it::

    python evals/run_evals.py            # offline, $0
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("COMPANION_MOCK", "1")

# Put the blueprint root (so `import app`) and the sibling eval-harness src on the path.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from app import _compose  # noqa: E402,F401 — side effect: adds sibling src/ to sys.path
from app import build_agent  # noqa: E402

from eval_harness import Case, Contains, load_jsonl, run  # type: ignore  # noqa: E402

_GOLDEN = _HERE / "faithfulness_golden.jsonl"


def build_candidate():
    """Return a candidate ``(case_input) -> output_text`` over the sample corpus.

    A case's ``input`` is a sub-question query; the candidate runs the agent's retrieval worker
    on it and returns the concatenated ``[source-id]`` citations of the evidence it gathered.
    The :class:`Contains` grader then checks the expected source id is among them (coverage).
    """
    agent = build_agent()

    def candidate(query: str) -> str:
        evidence = agent.worker.gather(query)
        return " ".join(ev.citation for ev in evidence)

    return candidate


def faithfulness_case() -> tuple[float, int, int]:
    """Run the full agent once and return (faithfulness, supported, total) for the headline."""
    agent = build_agent()
    report = agent.run("Should we acquire Acme Vector DB Inc.?")
    r = report.reflection
    return r.faithfulness, len(r.supported), r.total


def main() -> int:
    cases: list[Case] = load_jsonl(_GOLDEN)
    candidate = build_candidate()

    # Coverage grade: each case's `expected` source id must appear in the retrieved citations.
    report = run(candidate, cases, Contains(), threshold=0.5)
    print(report.render())

    # Faithfulness headline from a full run (the reflection pass scoring itself).
    faith, supported, total = faithfulness_case()
    print("")
    print("Faithfulness (full run)")
    print("-" * 40)
    print(f"supported claims: {supported}/{total}  ({faith:.0%})")

    # CI gate: coverage must pass AND the brief must be fully grounded.
    coverage_ok = report.pass_rate >= 1.0
    faithful_ok = faith >= 1.0
    ok = coverage_ok and faithful_ok
    print("")
    print("PASS" if ok else "FAIL", "— coverage", f"{report.pass_rate:.0%}", "faithfulness", f"{faith:.0%}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
