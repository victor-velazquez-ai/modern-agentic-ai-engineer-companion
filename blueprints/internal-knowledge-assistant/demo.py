#!/usr/bin/env python3
"""Runnable demo — the permissioned knowledge assistant, MOCK by default (no API spend).

The whole point in one screen: **the same question returns different evidence for different
identities, because the corpus is filtered to the caller BEFORE retrieval.**

Run it::

    python demo.py

``COMPANION_MOCK`` defaults to ``1`` (the repo-wide offline switch): the embedder/reranker are
deterministic mocks, the "model" is a grounded extractive stand-in, and the ticket tool is an
in-process MCP server. No network, no keys, no spend. Set ``COMPANION_MOCK=0`` and inject
gateway-backed ports (see the README) to go live; the composition does not change.

What you'll see:

1. **The breach test.** A query that targets the RESTRICTED compensation sheet, asked first as a
   regular employee (alice) and then as finance leadership (dana). The restricted doc is invisible
   to alice and visible to dana — same question, different result.
2. **A normal grounded answer** with inline citations from the all-hands corpus.
3. **Optional light tool use:** when the KB can't answer, the agent-loop files a ticket through
   the MCP-guarded ``file_ticket`` tool.
4. **A trace** of one answered question (observability-stack), so a bad answer is debuggable.
5. **Corpus freshness:** which documents are past the staleness budget and need a re-sync.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run straight from a clone without installing anything. Add this package and the sibling
# pattern blueprints' src/ dirs to the path. (kb_assistant also self-wires, so importing it is
# enough; we add the package root here so `app` / `ingest` import as packages.)
_THIS_DIR = Path(__file__).resolve().parent
_BLUEPRINTS = _THIS_DIR.parent
for _p in (
    _THIS_DIR,
    _BLUEPRINTS / "observability-stack" / "src",
):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.identity import IdentityProvider  # noqa: E402
from app.kb_assistant import Answer, KnowledgeAssistant  # noqa: E402
from app.freshness import check_freshness  # noqa: E402
from app.ticket_tool import filed_tickets, reset_tickets  # noqa: E402
from ingest.sync_acl import build_index, load_corpus  # noqa: E402

CORPUS_DIR = _THIS_DIR / "data" / "corpus"

RESTRICTED_QUESTION = "What is the PHOENIXLEDGER compensation multiplier and the L5 salary band?"
ANSWERABLE_QUESTION = "How many PTO days can I carry over to next year?"
UNANSWERABLE_QUESTION = "Can you order me a new standing desk and a 4K monitor?"

RULE = "=" * 78


def _show_answer(answer: Answer) -> None:
    print(answer.text)
    if answer.citations:
        print("  citations:")
        for i, c in enumerate(answer.citations, start=1):
            print(f"    [{i}] {c.title}  ({c.source})")
    print(f"  (docs you can see: {answer.visible_docs}; chunks retrieved: {answer.retrieved})")


def main() -> int:
    mock = os.getenv("COMPANION_MOCK", "1")
    print(RULE)
    print(f" Internal Knowledge Assistant demo  (COMPANION_MOCK={mock}, offline, no spend)")
    print(RULE)

    reset_tickets()  # reproducible across runs

    identity = IdentityProvider()
    store = build_index(load_corpus(CORPUS_DIR))
    assistant = KnowledgeAssistant(store, top_k=3)

    alice = identity.resolve("alice")  # regular employee
    dana = identity.resolve("dana")    # finance leadership

    # --- 1) THE BREACH TEST: same question, two identities, different evidence ---------------
    print("\n1) PERMISSION FILTER — same question, two identities")
    print("-" * 78)
    print(f"Q (as {alice.display_name}):\n  {RESTRICTED_QUESTION}\n")
    a_ans = assistant.ask(RESTRICTED_QUESTION, alice)
    _show_answer(a_ans)
    # Two ways a breach could show up: the secret in the prose, or the restricted doc in the
    # citations. The filter-before-retrieval rule makes both impossible for alice.
    leaked_alice = (
        "PHOENIXLEDGER" in a_ans.text
        or any(c.doc_id == "compensation-sheet" for c in a_ans.citations)
    )
    print(f"  -> restricted content leaked to alice? {leaked_alice}  "
          f"(must be False)")

    print(f"\nQ (as {dana.display_name}):\n  {RESTRICTED_QUESTION}\n")
    d_ans = assistant.ask(RESTRICTED_QUESTION, dana)
    _show_answer(d_ans)
    # "Can see it" means the restricted doc reached the cited evidence for dana — provenance,
    # not whether the truncated snippet happens to contain the codename.
    saw_dana = any(c.doc_id == "compensation-sheet" for c in d_ans.citations)
    print(f"  -> finance leadership can cite the comp sheet? {saw_dana}  (should be True)")

    # The headline assertion the demo exists to prove.
    assert not leaked_alice, "BREACH: restricted content leaked to an unprivileged identity"
    assert saw_dana, "the authorized identity should be able to read the restricted doc"
    print("\n  PASS: the restricted doc is invisible to alice and visible to dana.")

    # --- 2) a normal grounded answer with citations -----------------------------------------
    print("\n2) GROUNDED ANSWER — from the all-hands corpus, with citations")
    print("-" * 78)
    print(f"Q (as {alice.display_name}):\n  {ANSWERABLE_QUESTION}\n")
    _show_answer(assistant.ask(ANSWERABLE_QUESTION, alice))

    # --- 3) optional light tool use: escalate via the agent-loop + MCP ticket tool ----------
    print("\n3) ESCALATION — agent-loop files a ticket through the MCP-guarded tool")
    print("-" * 78)
    print(f"Q (as {alice.display_name}):\n  {UNANSWERABLE_QUESTION}\n")
    confirmation = assistant.escalate(UNANSWERABLE_QUESTION, alice)
    print(confirmation)
    tickets = filed_tickets()
    print(f"  -> tickets filed: {len(tickets)} "
          f"({tickets[-1]['id'] if tickets else 'none'} by {alice.user_id})")

    # --- 4) a trace of one answered question (observability-stack) ---------------------------
    print("\n4) TRACE — one answered question as a span tree (debug a bad answer)")
    print("-" * 78)
    try:
        from observability_stack import ConsoleExporter, Tracer

        tracer = Tracer()
        traced_assistant = KnowledgeAssistant(store, top_k=3, tracer=tracer)
        traced_assistant.ask(ANSWERABLE_QUESTION, alice)
        ConsoleExporter().export(tracer.trace)
    except Exception as exc:  # observability-stack optional; never break the demo
        print(f"  (observability-stack not available: {exc})")

    # --- 5) corpus freshness — so the knowledge base doesn't silently rot --------------------
    print("\n5) FRESHNESS — which docs are past the staleness budget")
    print("-" * 78)
    report = check_freshness(CORPUS_DIR)
    print(report.render())

    print("\n" + RULE)
    print(" OK — permission filter held, answer grounded, ticket filed, no API spend.")
    print(RULE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
