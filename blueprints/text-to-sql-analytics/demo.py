"""MOCK-mode demo — ask the warehouse questions in plain English, see the answer *and the SQL*.

Run it (free, offline, no API spend)::

    python data/build_warehouse.py   # once, to (re)build the bundled mock warehouse
    python demo.py                    # ask a few questions; or:  python demo.py "your question"

What you are watching is the SOLUTION composing four PATTERN blueprints end to end:

    rag-pipeline   ground NL on the semantic layer's schema/metric docs   (Ch 13)
        |
    generate       NL -> structured, schema-valid SqlPlan                 (Ch 15)
        |
    verify         read-only? schema-grounded? bounded?  -- BEFORE run    (Ch 16)
        |
    agent-loop     run the verified SQL as the loop's single tool         (Ch 12, 41)
        |
    observability  every stage traced with SQL + cost + row counts        (Ch 23)

It is treated as a **copilot, not an oracle**: every answer prints the SQL behind it (Ch 20), so a
human can read, trust, or correct the query. After the questions, the demo hands the verifier a few
*raw* unsafe queries (the kind a live LLM might hallucinate) to show the read-only / schema /
bounded contract blocking them before execution — a safe refusal, not a crash.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from app.pipeline import AnalyticsCopilot  # noqa: E402
from app.run import DEFAULT_DB  # noqa: E402

# The default questions the demo walks through (pick ones that exercise different patterns).
DEMO_QUESTIONS = [
    "What was our total revenue?",            # metric expansion (refund-correct)
    "Show revenue by region",                 # join + group-by + ordering
    "What is the average order value in EMEA?",  # filter + metric
    "How many signups by plan?",              # different table, different metric
]

# Raw queries the VERIFIER must refuse — the kind a live LLM might emit. These bypass the trusted
# mock planner on purpose, so we test the safety contract where it actually lives (Ch 16, 41).
UNSAFE_QUERIES = [
    "SELECT 1; DROP TABLE orders LIMIT 1",       # second statement / DROP
    "DELETE FROM orders WHERE 1=1",              # mutation against a read-only contract
    "SELECT orders.amount_usd FROM orders",      # no LIMIT -> cost guard
    "SELECT orders.profit FROM orders LIMIT 10", # hallucinated column
]

_BANNER = "=" * 78


def _ensure_warehouse() -> None:
    if not Path(DEFAULT_DB).exists():
        print("Mock warehouse not found — building it now...")
        # Import lazily so the demo has a single obvious entrypoint.
        sys.path.insert(0, str(_HERE / "data"))
        import build_warehouse  # type: ignore  # noqa: E402

        build_warehouse.build()
        print()


def run_demo(questions: list[str], *, show_trace: bool = True) -> None:
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    print(_BANNER)
    print("Talk-to-Your-Data Analytics Copilot — MOCK demo" if mock else "LIVE mode")
    print(f"mode: {'MOCK (free, offline, deterministic)' if mock else 'LIVE'}   "
          f"warehouse: {DEFAULT_DB.name}")
    print(_BANNER)

    copilot = AnalyticsCopilot()
    for i, question in enumerate(questions, start=1):
        answer = copilot.ask(question, trace=show_trace)
        print(f"\n[{i}] {answer.render()}")
        if show_trace and answer.trace_text:
            print("\n  trace:")
            print("\n".join("    " + line for line in answer.trace_text.splitlines()))
        print("\n" + "-" * 78)


def run_safety_demo(copilot: AnalyticsCopilot, queries: list[str]) -> None:
    print("\n" + _BANNER)
    print("Safety: raw unsafe queries the verifier refuses BEFORE execution (Ch 16, 41)")
    print(_BANNER)
    for q in queries:
        answer = copilot.check_sql(q)
        verdict = "BLOCKED" if answer.verify.blocked else "ALLOWED (!)"
        print(f"\n  [{verdict}] {q}")
        print(f"    {answer.verify.explain()}")


def main(argv: list[str]) -> int:
    _ensure_warehouse()
    questions = [" ".join(argv)] if argv else DEMO_QUESTIONS
    # A single ad-hoc question gets the trace; the full walkthrough keeps it for teaching value.
    run_demo(questions, show_trace=True)
    if not argv:
        run_safety_demo(AnalyticsCopilot(), UNSAFE_QUERIES)
    print("\nDone. Every answer above shows the SQL behind it — copilot, not oracle.")
    print("Next: `python evals/run_evals.py` to grade question -> expected rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
