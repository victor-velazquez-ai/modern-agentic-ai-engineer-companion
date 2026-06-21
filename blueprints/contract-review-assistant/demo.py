#!/usr/bin/env python
"""Runnable demo — review sample contracts end to end (MOCK by default, $0).

Run it::

    python demo.py                   # offline, deterministic, zero API spend (COMPANION_MOCK=1)
    COMPANION_MOCK=0 python demo.py  # live path IF the pattern blueprints are wired to a keyed gateway

What it shows, on three committed sample contracts:
  1. **extract** — split each contract into typed, validated clauses           (clause_schema · Ch 15)
  2. **flag**    — flag only the clauses that DEVIATE, each carrying a CITATION (flags · rag-pipeline · Ch 13)
  3. **redline** — for every flag, the agent PROPOSES an aligned edit          (review · agent-loop · Ch 16)
  4. **dispose** — a human accepts / edits / rejects each proposal             (HITL — the lawyer decides)
  5. **trace**   — the whole run is one audit trace: flag -> rule -> redline    (observability-stack · Ch 23)

The agent never accepts anything: every proposal starts PENDING and stays there until a person acts.
That is the product, not a setting. No module imports an SDK or spends a token in the default mode.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the solution package importable without installation (study & adapt, not a wheel). The
# `app` package's own `_compose` then puts the four composed pattern blueprints on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import (  # noqa: E402
    Decision,
    PlaybookIndex,
    review_contract,
)

try:  # observability is optional; the demo still runs (untraced) if the sibling is absent.
    from observability_stack import ConsoleExporter, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover - only when the sibling blueprint is missing
    _HAVE_OBS = False

_DATA_DIR = Path(__file__).resolve().parent / "data" / "contracts"

# The committed sample set: one clean contract (no flags expected), one riddled with red flags, and
# one realistic mix. Reviewing all three shows the assistant raises flags ONLY where a clause
# actually deviates — false positives erode a reviewer's trust as fast as misses do.
SAMPLE_CONTRACTS = (
    "saas-agreement-clean.txt",
    "vendor-msa-redflags.txt",
    "services-agreement-mixed.txt",
)


def _banner(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _load(name: str) -> tuple[str, str]:
    """Return ``(doc_id, text)`` for a sample contract; doc_id is the filename stem."""
    path = _DATA_DIR / name
    return path.stem, path.read_text(encoding="utf-8")


def _review_one(doc_id: str, text: str, index: PlaybookIndex) -> None:
    """Review one contract and print clauses -> cited flags -> redline proposals -> disposition."""
    tracer = Tracer() if _HAVE_OBS else None

    # One root RUN span per contract, so every redline CHAIN span hangs under an auditable root.
    if tracer is not None:
        with tracer.run(f"review:{doc_id}"):
            result = review_contract(doc_id, text, index=index, tracer=tracer)
    else:
        result = review_contract(doc_id, text, index=index)

    print(f"\nExtracted {len(result.clauses)} clauses; "
          f"{len(result.flags)} flagged as non-standard.")

    if not result.flags:
        print("  No deviations found — this contract tracks the playbook. Nothing to escalate.")
    else:
        print("\n  Cited flags (uncited flags are impossible by construction):")
        for f in result.flags:
            print(f"   • {f.cite()}")
            print(f"     {f.message}")

    if result.proposals:
        print("\n  Proposed redlines (all PENDING — the lawyer disposes):")
        for p in result.proposals:
            assert p.decision is Decision.PENDING  # the agent never advances past PENDING
            print(f"   • [{p.flag.rule_id}] clause {p.clause_id}")
            print(f"       was: {_clip(p.original_text)}")
            print(f"       new: {_clip(p.proposed_text)}")
            print(f"       why: {p.rationale}")

    _demo_human_in_the_loop(result)

    # The audit trace: flag -> rule -> redline, rolled-up cost ($0 in MOCK). This is the posture the
    # PLAN requires — every machine-proposed change is traceable to the rule that motivated it.
    if tracer is not None and tracer.root is not None:
        print("\n  Audit trace:")
        ConsoleExporter().export(tracer.trace)


def _demo_human_in_the_loop(result) -> None:
    """Show the three dispositions on the pending proposals — accept, edit, reject.

    In a real product these calls come from a review UI (Ch 20/38: accept/edit/reject), never from
    the agent. We simulate a reviewer here only to demonstrate that the decision is theirs and that
    each disposition produces a new, frozen, audit-friendly record.
    """
    pending = result.pending
    if not pending:
        return
    print("\n  Human-in-the-loop (simulated reviewer disposition):")
    dispositions = (
        ("accept", lambda p: p.accept()),
        ("edit",   lambda p: p.edit(p.proposed_text + " [counsel: scope to direct damages only]")),
        ("reject", lambda p: p.reject()),
    )
    for i, p in enumerate(pending):
        label, act = dispositions[i % len(dispositions)]
        disposed = act(p)
        print(f"   • {p.clause_id}: lawyer chose to {label.upper()} -> "
              f"decision={disposed.decision}; final text wins, agent's proposal kept for audit.")


def _clip(text: str, width: int = 88) -> str:
    """One-line preview of a clause/redline for the console."""
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def main() -> None:
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    print("Modern Agentic AI Engineer — contract-review-assistant (SOLUTION blueprint)")
    print(f"MOCK mode: {'ON (offline, deterministic, $0)' if mock else 'OFF (live)'}")
    print("Composes: agent-loop · rag-pipeline · eval-harness · observability-stack")
    print("The agent PROPOSES; a lawyer DISPOSES. No uncited flags. No auto-apply.")

    # Build the playbook retrieval index ONCE and reuse it across every contract — the same
    # rag-pipeline index grounds every flag, so a citation always points at a real playbook rule.
    index = PlaybookIndex()
    print(f"\nPlaybook loaded: {len(index.rules)} risk rules indexed for grounded retrieval.")

    for name in SAMPLE_CONTRACTS:
        doc_id, text = _load(name)
        _banner(f"CONTRACT: {name}")
        _review_one(doc_id, text, index)

    print("\nDone. Every flag above cites a playbook rule; every redline is still PENDING a human.")
    print("Adapt it: swap playbook/risk_rules.md + clause_schema.py for your domain (see README.md).")


if __name__ == "__main__":
    main()
