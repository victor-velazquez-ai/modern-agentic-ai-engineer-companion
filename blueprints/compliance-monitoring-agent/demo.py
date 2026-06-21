#!/usr/bin/env python
"""Runnable demo — screen a mock stream, flag with rule citations, write the audit trail.

    python demo.py                  # MOCK mode (default): offline, deterministic, zero API spend
    COMPANION_MOCK=0 python demo.py # would inject an llm-gateway model into the classifier (live)

This is the **solution** blueprint for Appendix-G #12 (Compliance & monitoring agent). It does not
invent new mechanism — it *composes four pattern blueprints* (no forks, imported from
``../<pattern>/src``):

  rag-pipeline        -> retrieve the policy rule each flag must cite        (app/policy_check.py)
  agent-loop          -> structured, confidence-bearing clear/flag verdict  (app/classify.py)
  observability-stack -> the run trace (cost/timing) around the pass         (app/screen.py)
  eval-harness        -> the precision/recall-tuned golden set               (evals/)

and adds the two things that make it a compliance *product*: a **human adjudication queue**
(the agent flags and routes; humans decide) and an **append-only, hash-chained audit ledger**
(tamper-evident record of every decision and its basis).

What you'll see, end to end:
  1. screen ~8 mock messages/transactions against the policy corpus;
  2. each flag cites the violated rule + shows the basis (the retrieved rule text);
  3. flags routed to a priority-ordered human review queue;
  4. an append-only audit ledger written and verified (hash chain intact);
  5. the observability trace tree + cost roll-up for the whole run ($0 in mock);
  6. the eval golden set scored, broken down by precision (must-clear) and recall (must-flag).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Read-it-by-running-it: make this package importable without an install step.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import add_blueprint_paths, mock_mode  # noqa: E402
from app.route import ReviewStatus, severity_for  # noqa: E402
from app.screen import Screener, classify_label  # noqa: E402
from audit.ledger import AuditLedger  # noqa: E402

add_blueprint_paths()

from eval_harness import Case, ExactMatch, parse_case, run  # noqa: E402
from observability_stack import ConsoleExporter, summarize  # noqa: E402

HERE = Path(__file__).resolve().parent
STREAM_PATH = HERE / "data" / "stream" / "messages.jsonl"
GOLDEN_PATH = HERE / "evals" / "flags_golden.jsonl"


def _banner(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def _load_jsonl(path: Path) -> list[dict]:
    """Load a '#'-commented JSONL file into a list of dicts (blank/comment lines skipped)."""
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(json.loads(line))
    return items


def screen_the_stream() -> tuple[Screener, list]:
    """Run the composed screening pass over the mock stream; return the screener + results."""
    items = _load_jsonl(STREAM_PATH)

    # The append-only audit ledger is the product. Mirror it to dist/ so you can inspect/verify it.
    ledger_path = HERE / "dist" / "audit-ledger.jsonl"
    ledger_path.parent.mkdir(exist_ok=True)
    if ledger_path.exists():
        ledger_path.unlink()  # fresh trail per demo run (the file itself stays append-only mid-run)
    ledger = AuditLedger(path=ledger_path)

    screener = Screener.build(ledger=ledger)
    results = screener.screen_stream(items)

    _banner("1) Screening results — every flag cites the rule it broke")
    for r in results:
        mark = "FLAG" if r.flagged else "ok  "
        rule = f"[{r.assessment.rule_id}]" if r.flagged else "[--]"
        print(f"  {mark} {r.item_id}  {rule:<10} conf={r.assessment.confidence:.2f}")
        print(f"        {r.item_text[:78]}")
        if r.flagged:
            cited = screener.policy_index.rule(r.assessment.rule_id)
            title = cited.title if cited else r.match.title
            basis = (cited.text if cited else r.match.snippet)
            print(f"        -> cites {r.assessment.rule_id} ({title})")
            print(f"        -> basis: {basis[:96].strip()}...")
        if r.anomaly is not None:
            print(f"        -> anomaly: {r.anomaly.reason}")
    return screener, results


def show_review_queue(screener: Screener) -> None:
    """Show the human adjudication queue and demonstrate a human adjudicating two tickets."""
    _banner("2) Human adjudication queue — the agent routes; a human decides")
    print(f"  {len(screener.queue.pending)} flagged item(s) awaiting review (priority order):\n")
    for t in screener.queue.pending:
        print(
            f"  P{t.priority:>4.1f}  {t.item_id}  [{t.rule_id}] sev={severity_for(t.rule_id)} "
            f"conf={t.confidence:.2f}  status={t.status}"
        )

    # A human adjudicates the top two (this is the only place a *decision* is made).
    pending = list(screener.queue.pending)
    if pending:
        pending[0].adjudicate(confirmed=True, note="Confirmed by analyst — escalated to compliance.")
        if len(pending) > 1:
            pending[1].adjudicate(confirmed=False, note="Dismissed — false positive on review.")
        print("\n  (human action) top tickets adjudicated:")
        for t in pending[:2]:
            print(f"    {t.item_id} [{t.rule_id}] -> {t.status}: {t.resolution_note}")


def show_audit_trail(screener: Screener) -> None:
    """Print the append-only audit ledger and verify its hash chain is intact."""
    _banner("3) Audit trail — append-only, hash-chained, tamper-evident (Ch 28)")
    ledger: AuditLedger = screener.ledger
    print(f"  {len(ledger)} records written; chain verify -> {ledger.verify()}\n")
    for rec in ledger:
        cite = f"[{rec.rule_id}]" if rec.decision == "flag" else "[--]"
        print(
            f"  #{rec.seq} {rec.item_id} {rec.decision.upper():<5} {cite:<10} "
            f"conf={rec.confidence:.2f} routed={rec.routed_to}  hash={rec.record_hash[:12]}…"
        )
    print(f"\n  Durable trail written to: {ledger.path}")
    print("  Tamper-evidence: edit any earlier record and verify() returns False "
          "(every later prev_hash breaks).")


def show_trace_and_cost(screener: Screener) -> None:
    """Render the observability trace tree + the run cost roll-up ($0 in mock)."""
    _banner("4) Observability — the run as a trace tree + cost roll-up")
    ConsoleExporter(show_tokens=False).export(screener.tracer.trace)
    summary = summarize(screener.tracer.trace)
    print(f"\n  model calls: {summary.llm_call_count}   "
          f"total cost: ${summary.total_usd:.6f} (mock model prices to $0)")


def run_evals() -> None:
    """Score the screener against the precision/recall-tuned golden set (eval-harness)."""
    _banner("5) Evals — precision/recall on the expert-labeled golden set (Ch 22)")
    rows = _load_jsonl(GOLDEN_PATH)
    cases: list[Case] = [parse_case(row) for row in rows]

    # The candidate IS the shipped decision path (app.screen.classify_label), graded on the label.
    report = run(classify_label, cases, ExactMatch(), threshold=1.0)
    print(report.render())

    tags = report.by_tag()
    recall = tags.get("must-flag")
    precision = tags.get("must-clear")
    print()
    if recall:
        print(f"  recall    (must-flag) : {recall.pass_rate:.0%}  "
              f"-> a miss here is a regulatory failure")
    if precision:
        print(f"  precision (must-clear): {precision.pass_rate:.0%}  "
              f"-> a miss here buries the review team in false positives")
    print("\n  Tune this trade-off WITH compliance experts; gate the build on it "
          "(eval_harness.gate).")


def main() -> int:
    # The eval report renders ✓/✗ glyphs; make them printable on cp1252 (Windows) consoles too.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
            pass

    mode = "MOCK (offline, deterministic, $0)" if mock_mode() else "LIVE"
    print("Modern Agentic AI Engineer — compliance-monitoring-agent (SOLUTION blueprint)")
    print(f"Composes: rag-pipeline · agent-loop · eval-harness · observability-stack | mode: {mode}")

    screener, _results = screen_the_stream()
    show_review_queue(screener)
    show_audit_trail(screener)
    show_trace_and_cost(screener)
    run_evals()

    print("\nNext: swap policy/policies.md for your corpus, wire connectors to your streams, "
          "and tune the evals with your compliance team. See README.md.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("COMPANION_MOCK", "1")  # never spend behind the caller's back
    raise SystemExit(main())
