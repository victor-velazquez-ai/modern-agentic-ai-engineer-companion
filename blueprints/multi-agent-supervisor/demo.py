"""Runnable demo: a 2-worker team (researcher + writer) finishes a task.

Runs **offline by default** (``COMPANION_MOCK=1``) — no API key, no spend, deterministic
output. Set ``COMPANION_MOCK=0`` and export ``ANTHROPIC_API_KEY`` to hit a live model.

    python demo.py
    python demo.py "Compare RAG and fine-tuning, then write a short recommendation"

What it shows
-------------
* The supervisor plans a task into research → write sub-tasks.
* Independent research sub-tasks fan out in parallel and rejoin.
* Worker outputs aggregate into one final answer.
* The supervisor reports *why* it stopped (done / degraded / guard-tripped).
* A second run injects a failing worker to show graceful degradation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running straight from the blueprint with no install: add src/ to the path.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

try:  # optional, per NOTEBOOK-STANDARDS §3 (load_dotenv if present)
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv is optional; absence must not break the demo.
    pass

from multi_agent_supervisor import (  # noqa: E402 (after sys.path setup)
    DoneReason,
    MockModel,
    Supervisor,
    Worker,
    default_team,
    mock_enabled,
)


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run_happy_path(task: str) -> None:
    _banner(f"Supervisor run  (MOCK={'on' if mock_enabled() else 'OFF — live API'})")
    print(f"Task: {task}\n")

    sup = Supervisor.from_team(parallel=True)  # honors COMPANION_MOCK
    result = sup.run(task)

    print("Plan:")
    for st in result.plan:
        dep = f"  ← depends on {', '.join(st.depends_on)}" if st.depends_on else ""
        print(f"  [{st.id}] ({st.capability}) {st.description}{dep}")

    print("\nWorker contributions:")
    for c in result.report.contributions:
        tools = f"  tools={list(c.tools_used)}" if c.tools_used else ""
        print(f"  - {c.worker} ({c.role}){tools}")

    print(f"\nDecision: {result.reason.value}  ·  tokens≈{result.report.total_tokens}  ·  iterations={result.iterations}")
    print("\nFinal answer:\n")
    print(result.answer)


def run_degraded_path(task: str) -> None:
    _banner("Failure isolation  (one worker is wired to crash)")

    class FlakyModel(MockModel):
        def complete(self, prompt, *, system=None, role=None):  # type: ignore[override]
            if "research" in (role or ""):
                raise RuntimeError("research backend timeout")
            return super().complete(prompt, system=system, role=role)

    model = FlakyModel()
    workers: list[Worker] = default_team(model)
    sup = Supervisor(workers=workers, model=model, parallel=True)
    result = sup.run(task)

    print(f"Decision: {result.reason.value}  (degraded={result.report.degraded})")
    print(f"Failures: {list(result.report.failures)}")
    print("\nStill produced an answer:\n")
    print(result.answer)
    assert result.reason is DoneReason.DEGRADED, "expected graceful degradation"
    print("\nThe team degraded instead of crashing. ✔")


def main() -> int:
    task = sys.argv[1] if len(sys.argv) > 1 else (
        "Explain what a vector database is and write a two-sentence summary"
    )
    if not mock_enabled() and not os.getenv("ANTHROPIC_API_KEY"):
        print("COMPANION_MOCK=0 but ANTHROPIC_API_KEY is unset. Set the key or unset COMPANION_MOCK.")
        return 1

    run_happy_path(task)
    run_degraded_path(task)
    _banner("Done. Re-run with COMPANION_MOCK=0 + ANTHROPIC_API_KEY for the live path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
