"""End-to-end MOCK demo: transcript -> conservative CRM update -> drafted, UNSENT outreach.

Run it::

    python demo.py            # from this folder (sales-revops-automation/)

It runs **free, offline, and deterministically** (``COMPANION_MOCK=1``, the default): no network,
no API keys, no spend. It walks one account end to end and then the nightly jobs, exercising every
composed pattern blueprint:

  call_to_crm   (agent-loop + mcp-server)  transcript -> confidence-scored fields -> conservative write
  enrich        (mcp-server)               fill empty firmographics via the guarded boundary
  draft_outreach(rag-pipeline + agent-loop)grounded follow-up + wrong-recipient guardrail, UNSENT
  schedules     (observability-stack)      nightly enrichment + read-only pipeline hygiene, traced

The two things to watch for, the PLAN's locked decisions:

  * the **flagged** (withheld) low-confidence field — bad data in the forecast is worse than
    missing data, so a hedged amount is surfaced for a human, never written; and
  * the email's **status: draft** and the wrong-recipient guardrail HOLDING a mis-addressed draft —
    a human sends, the agent never does.

To go live, set ``COMPANION_MOCK=0`` and inject a gateway-backed model/embedder (see the README and
each module's docstring). Nothing in the control flow below changes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Run free by default. Set COMPANION_MOCK=0 in the env (and wire a gateway) for the live path.
os.environ.setdefault("COMPANION_MOCK", "1")

# Make this folder importable as the package root so ``revops`` / ``workflow`` / ``tools`` resolve
# when the demo is run directly (``python demo.py``) from a fresh clone.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from revops.compose import data_dir  # noqa: E402
from tools.crm_mock import CRMStore  # noqa: E402
from workflow.call_to_crm import process_call  # noqa: E402
from workflow.draft_outreach import build_messaging_index, draft_followup  # noqa: E402
from workflow.enrich import enrich_account  # noqa: E402
from workflow.schedules import nightly_enrichment, pipeline_hygiene  # noqa: E402


def _rule(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _load_call(stem: str) -> dict:
    return json.loads((data_dir() / "calls" / f"{stem}.json").read_text(encoding="utf-8"))


def main() -> int:
    # Render the ✓/x glyphs on any console (incl. Windows cp1252).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    print(f"Sales & RevOps automation — MOCK demo  (COMPANION_MOCK={'1' if mock else '0'})")
    print("Composes: agent-loop · rag-pipeline · mcp-server · eval-harness · observability-stack")

    # One shared in-memory CRM so every stage reads/writes the *same* accounts (as in production).
    store = CRMStore()

    # --- 1. Two calls -> CRM (agent-loop + mcp-server, conservative write) ----------------------
    _rule("1. call_to_crm  —  transcript -> structured CRM update (conservative)")
    for stem in ("globex-002-proposal", "acme-001-discovery"):
        call = _load_call(stem)
        result = process_call(call, store=store)
        print(f"\nAccount {result.account_id}  (from {stem})")
        print(f"  written to CRM : {result.applied or '(nothing)'}")
        if result.flagged:
            for f in result.flagged:
                print(f"  FLAGGED (held) : {f['field']}={f.get('value')!r}  — {f['reason']}")
        else:
            print("  flagged        : (none)")
    print(
        "\n  ^ Acme's amount was HELD: the buyer hedged on finance sign-off, so it is left for a"
        "\n    human, not written. Bad data in the forecast is worse than missing data."
    )

    # --- 2. Enrich an incomplete record (mcp-server, fills empty fields only) -------------------
    _rule("2. enrich  —  fill empty firmographics via the guarded MCP boundary")
    enriched = enrich_account("acme-001", store=store)
    print(f"\nAccount {enriched.account_id}  (domain {enriched.domain}, provider found={enriched.found})")
    print(f"  filled empty fields : {enriched.applied or '(nothing to fill)'}")
    print("  ^ enrichment only fills EMPTY slots; it never overwrites a human-entered value.")

    # --- 3. Draft outreach (rag-pipeline + agent-loop, grounded, UNSENT) ------------------------
    _rule("3. draft_outreach  —  grounded follow-up, DRAFTED for a human to send")
    index = build_messaging_index()  # ingest the winning-messaging playbook once (rag-pipeline)

    account = store.get_account("globex-002")
    draft = draft_followup(account, retriever=index)
    print(f"\nDraft for {draft.account_id}  ->  to: {draft.to}   [status: {draft.status}]")
    print(f"  subject : {draft.subject}")
    print("  body    :")
    for line in draft.body.splitlines():
        print(f"    {line}")
    print(f"  grounded on playbook sources: {draft.source_ids()}")
    print("  ^ status is 'draft' — the rep reviews and sends. The agent never sends.")

    # The wrong-recipient guardrail: try to draft to a foreign-domain address -> HELD, not composed.
    _rule("3b. wrong-recipient guardrail  —  a mis-addressed draft is HELD")
    held = draft_followup(account, to="buyer@competitor.com", retriever=index)
    print(f"\nAttempt to draft to buyer@competitor.com  ->  [status: {held.status}]")
    print(f"  hold_reason : {held.hold_reason}")
    print("  ^ no draft was composed to the wrong company — mis-sending is the costliest failure.")

    # --- 4. Background jobs (observability-stack, traced) ---------------------------------------
    _rule("4. schedules  —  nightly enrichment + read-only pipeline hygiene (traced)")
    # Fresh store so the nightly job has untouched records to enrich.
    nightly_store = CRMStore()
    enrich_report = nightly_enrichment(store=nightly_store)
    print("\n" + enrich_report.summary())
    for r in enrich_report.enriched:
        if r.applied:
            print(f"  {r.account_id}: filled {r.applied}")

    hygiene_report = pipeline_hygiene(store=CRMStore())
    print("\n" + hygiene_report.summary())
    for issue in hygiene_report.issues:
        print(f"  - {issue.account_id}: {issue.field}  ({issue.reason})")

    _rule("Done")
    print(
        "Every stage ran offline and free. The two outputs the PLAN's definition of done requires:"
        "\n  * a conservative CRM update (low-confidence fields flagged, not written), and"
        "\n  * a DRAFTED, UNSENT outreach email (human-on-send), with a wrong-recipient guardrail."
        "\nSwap COMPANION_MOCK=0 + a gateway client to run it live; the wiring above is unchanged."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
