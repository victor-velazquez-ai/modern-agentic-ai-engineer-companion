#!/usr/bin/env python3
"""Runnable demo — the customer-support solution end to end, MOCK by default.

Run it::

    python demo.py            # three tickets: deflect, act, escalate
    python demo.py --eval     # also run the golden-set eval gate (resolution, not deflection)

Everything runs **in one process with no network, no API keys, and no spend**.
``COMPANION_MOCK`` defaults to ``1`` (the repo-wide offline switch): retrieval uses the
deterministic mock embedder + reranker, the scoped tools run over an in-process MCP transport,
and the answer-only path synthesises a grounded reply from the top retrieved chunk instead of
calling a model. The *only* live-path seam is the answering model — route it through
``llm-gateway`` and set ``COMPANION_MOCK=0`` (with a key in the env) to enable it.

What you'll see, one block per ticket:

1. **DEFLECT**  — a password question answered from the help center, *with citations* (RAG).
2. **ACT**      — an in-policy refund executed through a scoped, gated MCP tool.
3. **ESCALATE** — an irreversible "delete my account" request handed to a human by policy.

Then (with ``--eval``) the golden set is scored and gated: the headline metric is **resolution**
(did the agent take the *right* action, with grounding when it answered), not raw deflection.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run straight from a clone: put this solution's own root on the path so ``app`` / ``tools`` /
# ``data`` import as packages, then let ``app._paths`` wire the sibling pattern blueprints.
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from app import _paths  # noqa: E402,F401  (side effect: sibling blueprints importable)
from app.decision import Action  # noqa: E402
from app.support_agent import SupportAgent  # noqa: E402
from data import load_help_center  # noqa: E402
from tools.billing_mock import build_support_client  # noqa: E402

try:  # observability is optional; the demo runs without it.
    from mcp_server import as_agent_tools  # noqa: E402,F401
    from observability_stack import ConsoleExporter, Tracer  # noqa: E402
except Exception:  # pragma: no cover
    Tracer = None  # type: ignore[assignment,misc]
    ConsoleExporter = None  # type: ignore[assignment,misc]


# The three canonical tickets — one per branch of the autonomy dial.
_TICKETS = [
    ("deflect", "Hi, I'm locked out and can't sign in — how do I reset my password?"),
    ("act", "Please refund $25 to account cus_001, the item arrived damaged."),
    ("escalate", "I want to delete my account and wipe all my data right now."),
]


def build_agent() -> SupportAgent:
    """Compose the solution: RAG over the help center + scoped MCP tools + escalation policy."""
    client = build_support_client()  # in-process MCP server + guarded client (handshake done)

    def tool_caller(name: str, args: dict) -> object:
        # The agent reaches tools ONLY through the safe client's guards (allow-list, validation,
        # timeout). This closure is the seam; nothing about the agent knows about transports.
        return client.call(name, args)

    docs = load_help_center()
    return SupportAgent.from_help_center(docs, tool_caller=tool_caller)


def _force_utf8_console() -> None:
    """Render the ·/— glyphs cleanly on any console (incl. Windows cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass


def run_tickets(agent: SupportAgent, *, trace: bool = False) -> int:
    _force_utf8_console()
    mock = os.getenv("COMPANION_MOCK", "1")
    print(f"== customer-support-agent demo (COMPANION_MOCK={mock}, in-process, no network) ==\n")

    tracer = Tracer() if (trace and Tracer is not None) else None
    for label, ticket in _TICKETS:
        decision = agent.handle(ticket, tracer=tracer)
        print(f"[{label.upper()}] ticket: {ticket}")
        print(f"  -> {decision.headline()}")
        print(f"     answer: {decision.answer}")
        if decision.action is Action.RESOLVE:
            srcs = ", ".join(f"{c.title} ({c.doc_id})" for c in decision.citations)
            print(f"     cited : {srcs}")
        if decision.action is Action.ACT:
            print(f"     result: {decision.tool_result}")
        print()

    if tracer is not None and ConsoleExporter is not None:
        print("-- one ticket's trace (observability-stack) --")
        agent.handle(_TICKETS[0][1], tracer=(t := Tracer()))
        ConsoleExporter().export(t.trace)
        print()

    print("OK - three tickets resolved (deflect / act / escalate), no API spend.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    agent = build_agent()
    code = run_tickets(agent, trace=("--trace" in argv))
    if "--eval" in argv:
        print("\n" + "=" * 60)
        from evals.run_eval import main as eval_main  # local import; keeps base demo light

        code = eval_main(agent=agent) or code
    return code


if __name__ == "__main__":
    os.environ.setdefault("COMPANION_MOCK", "1")
    raise SystemExit(main())
