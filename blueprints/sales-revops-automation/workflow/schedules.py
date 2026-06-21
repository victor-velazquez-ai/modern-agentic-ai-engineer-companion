"""Schedules: the background jobs that keep the pipeline clean (composes observability-stack).

The everyday RevOps win is not a chat window — it is the **work that happens while no one is
watching**: a nightly job that enriches the accounts that came in incomplete and flags the records
that have gone stale, so the morning pipeline is cleaner than the night before. This module is the
``schedules.py`` the PLAN calls out (Ch 31 background jobs), and it is fully **traced** with the
**``observability-stack``** blueprint (Ch 23): every account the job touches becomes a span under
the run, with the write report attached, so an operator can answer "what did the nightly job do,
and why?" from the trace alone.

Two jobs ship here:

* :func:`nightly_enrichment` — fill empty firmographic fields via :mod:`workflow.enrich` (which
  goes through the guarded MCP boundary and the conservative write).
* :func:`pipeline_hygiene` — read-only: surface records that look stale or under-filled (no
  ``next_step``, no ``amount`` past Discovery, etc.) for a human to fix. It *writes nothing* — a
  hygiene job that silently edited the forecast would be the very failure the PLAN warns against.

Everything is MOCK/offline and free: the tracer is stdlib-only, the CRM is the in-memory mock. A
real deployment runs these on cron/Temporal and swaps :class:`~observability_stack.ConsoleExporter`
for an OTLP/Phoenix/Langfuse exporter — the instrumentation does not change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from revops.compose import ensure_on_path

ensure_on_path()

from tools.crm_mock import CRMStore, connect_crm  # noqa: E402
from workflow.enrich import EnrichmentResult, enrich_account  # noqa: E402

try:  # observability is optional; degrade to a no-op tracer-less path if the sibling is absent.
    from observability_stack import ConsoleExporter, SpanKind, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover - exercised only when the sibling is missing
    _HAVE_OBS = False


# Stages at which an account is expected to carry a deal amount; missing one past Discovery is a
# hygiene smell worth a human's glance (not an auto-fix — we never invent a forecast number).
_STAGES_EXPECTING_AMOUNT = frozenset({"Proposal", "Negotiation", "Evaluation"})


@dataclass(frozen=True)
class HygieneIssue:
    """One stale / under-filled record a human should look at (read-only; never auto-fixed)."""

    account_id: str
    field: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"account_id": self.account_id, "field": self.field, "reason": self.reason}


@dataclass
class JobReport:
    """The outcome of one scheduled job run — what it touched, for the trace and the morning report."""

    job: str
    accounts_seen: int = 0
    enriched: list[EnrichmentResult] = field(default_factory=list)
    issues: list[HygieneIssue] = field(default_factory=list)

    @property
    def fields_filled(self) -> int:
        return sum(len(r.applied) for r in self.enriched)

    def summary(self) -> str:
        if self.job == "nightly_enrichment":
            return (
                f"{self.job}: scanned {self.accounts_seen} account(s), "
                f"filled {self.fields_filled} field(s) across "
                f"{sum(1 for r in self.enriched if r.applied)} record(s)."
            )
        return (
            f"{self.job}: scanned {self.accounts_seen} account(s), "
            f"flagged {len(self.issues)} hygiene issue(s) for review."
        )


def _new_tracer(name: str) -> "Tracer | None":
    return Tracer() if _HAVE_OBS else None


def nightly_enrichment(
    *, store: CRMStore | None = None, export: bool = False
) -> JobReport:
    """Enrich every account with empty firmographic fields. Traced; writes are conservative.

    For each account the job opens a span, runs :func:`workflow.enrich.enrich_account` (guarded MCP
    + conservative write), and records what was filled on the span. Pass ``export=True`` to print
    the trace tree + cost roll-up via the console exporter (what an operator reads).
    """
    store = store or CRMStore()
    client = connect_crm(store)
    # The account ids are the store's keys; read them via a snapshot through the boundary would
    # need a list tool — for the mock we read the store's seeded ids directly (the demo seam).
    account_ids = list(store._accounts.keys())  # noqa: SLF001 - in-process mock; see README

    report = JobReport(job="nightly_enrichment", accounts_seen=len(account_ids))
    tracer = _new_tracer("nightly_enrichment")

    def _run_one(account_id: str) -> None:
        result = enrich_account(account_id, store=store)
        report.enriched.append(result)

    if tracer is not None:
        with tracer.run("nightly_enrichment"):
            for account_id in account_ids:
                with tracer.span(f"enrich:{account_id}", SpanKind.CHAIN) as span:
                    _run_one(account_id)
                    last = report.enriched[-1]
                    span.set_attribute("found", last.found)
                    span.set_attribute("fields_filled", len(last.applied))
        if export and _HAVE_OBS:
            ConsoleExporter().export(tracer.trace)
    else:  # pragma: no cover - only when observability sibling is missing
        for account_id in account_ids:
            _run_one(account_id)

    return report


def pipeline_hygiene(*, store: CRMStore | None = None, export: bool = False) -> JobReport:
    """Read-only nightly scan: flag stale / under-filled records for a human (writes nothing).

    Heuristics (deterministic, cheap, tune to your pipeline):
      * no ``next_step`` on an open deal — the rep has no recorded commitment;
      * no ``amount`` once the deal is past Discovery — the forecast is missing a number;
      * no ``industry`` — enrichment hasn't filled it (a pointer to run :func:`nightly_enrichment`).

    Every finding is a :class:`HygieneIssue` for review. The job *never* writes — surfacing a gap
    is safe; guessing a value to fill it would poison the forecast.
    """
    store = store or CRMStore()
    account_ids = list(store._accounts.keys())  # noqa: SLF001 - in-process mock; see README

    report = JobReport(job="pipeline_hygiene", accounts_seen=len(account_ids))
    tracer = _new_tracer("pipeline_hygiene")

    def _check(account_id: str) -> None:
        acct = store.get_account(account_id)
        stage = str(acct.get("stage", ""))
        if not str(acct.get("next_step") or "").strip():
            report.issues.append(
                HygieneIssue(account_id, "next_step", "no recorded next step on an open deal")
            )
        if acct.get("amount") in (None, 0) and stage in _STAGES_EXPECTING_AMOUNT:
            report.issues.append(
                HygieneIssue(account_id, "amount", f"no amount at stage {stage!r}")
            )
        if not str(acct.get("industry") or "").strip():
            report.issues.append(
                HygieneIssue(account_id, "industry", "missing firmographics — run enrichment")
            )

    if tracer is not None:
        with tracer.run("pipeline_hygiene"):
            for account_id in account_ids:
                with tracer.span(f"hygiene:{account_id}", SpanKind.CHAIN) as span:
                    before = len(report.issues)
                    _check(account_id)
                    span.set_attribute("issues_found", len(report.issues) - before)
        if export and _HAVE_OBS:
            ConsoleExporter().export(tracer.trace)
    else:  # pragma: no cover - only when observability sibling is missing
        for account_id in account_ids:
            _check(account_id)

    return report
