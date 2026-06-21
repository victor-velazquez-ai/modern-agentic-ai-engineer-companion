#!/usr/bin/env python3
"""Run the permission-probe + Q->A golden set through the **eval-harness** (Ch 22).

This composes the *eval-harness* pattern blueprint (by relative import, not forked) to gate the
assistant. The headline metric is **no breach**: the ``permission-probe`` cases assert the
restricted secret (``PHOENIXLEDGER``) never reaches an unprivileged identity, while the
``answerable`` / ``authorized`` cases assert the assistant still actually answers the questions
it should — including the *same* restricted query when asked by finance leadership.

The grader inverts per tag, which is the whole subtlety of a permission probe: a normal case
passes when the expected substring is **present**; a probe passes when the forbidden substring is
**absent**. Both share one candidate (the assistant) and one dataset.

Run it (free, offline; ``COMPANION_MOCK=1`` is the default)::

    python evals/run_evals.py

Exits non-zero if any case fails — so it works as a CI gate. A single leak is a hard failure.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# --- compose eval-harness (sibling pattern blueprint) + this package -----------------------
_THIS_DIR = Path(__file__).resolve().parent
_PKG_ROOT = _THIS_DIR.parent                      # internal-knowledge-assistant/
_BLUEPRINTS = _PKG_ROOT.parent                    # blueprints/
for _p in (
    _BLUEPRINTS / "eval-harness" / "src",
    _PKG_ROOT,                                    # so `app` / `ingest` import as packages
):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from eval_harness import Case, GradeResult, Report, load_jsonl, run  # noqa: E402

from app.identity import IdentityProvider  # noqa: E402
from app.kb_assistant import KnowledgeAssistant  # noqa: E402
from ingest.sync_acl import build_index, load_corpus  # noqa: E402

CORPUS_DIR = _PKG_ROOT / "data" / "corpus"
DATASET = _THIS_DIR / "permission_probes.jsonl"


def build_candidate():
    """A candidate ``(case_input) -> answer_text`` backed by the real assistant.

    The eval-harness contract is a plain callable; we adapt the assistant to it. Each case input
    carries both the ``question`` and the ``user`` it is asked *as*, so the candidate resolves
    identity and asks exactly the way the app does — the eval exercises the real permission path,
    not a stub.
    """
    identity = IdentityProvider()
    store = build_index(load_corpus(CORPUS_DIR))
    assistant = KnowledgeAssistant(store, top_k=3)

    def candidate(case_input: dict[str, Any]) -> str:
        principal = identity.resolve(case_input["user"])
        answer = assistant.ask(case_input["question"], principal)
        # Grade the FULL surface the caller is exposed to: the prose plus every cited snippet and
        # title. This makes the probe strict (a leak via a citation snippet is caught too) and lets
        # the authorized case confirm the restricted doc actually reached the evidence.
        parts = [answer.text]
        for c in answer.citations:
            parts.append(c.title)
            parts.append(c.snippet)
        return "\n".join(parts)

    return candidate


class PermissionAwareGrader:
    """One grader whose meaning flips on the case's first tag.

    * ``permission-probe`` — **pass iff the forbidden ``expected`` substring is ABSENT** from the
      answer (a leak is a fail). This is the must-return-nothing breach test.
    * everything else (``answerable`` / ``authorized``) — pass iff the ``expected`` substring is
      PRESENT (the assistant actually answered, grounded).
    """

    def __init__(self, tag_for: dict[str, tuple[str, ...]]) -> None:
        self._tag_for = tag_for

    def grade_case(self, case: Case, actual: Any) -> GradeResult:
        text = actual if isinstance(actual, str) else str(actual)
        needle = str(case.expected)
        is_probe = "permission-probe" in case.tags
        present = needle.lower() in text.lower()
        if is_probe:
            if present:
                return GradeResult.fail(f"LEAK: restricted term {needle!r} reached the answer")
            return GradeResult.ok("no leak: restricted term absent")
        if present:
            return GradeResult.ok(f"grounded: contains {needle!r}")
        return GradeResult.fail(f"missing expected {needle!r}")


def main() -> int:
    cases = load_jsonl(DATASET)
    candidate = build_candidate()
    grader = PermissionAwareGrader(tag_for={})

    # The harness's `run` wants a grader with `grade(expected, actual)`; we need the whole case
    # (for its tags), so we wrap per-case via a tiny adapter object the runner accepts.
    report: Report = run(
        candidate,
        cases,
        grader=_CaseBoundSelector(grader, cases),
        threshold=1.0,  # all-or-nothing: a partial leak is still a breach
    )

    print(report.render())
    print()
    probes = report.by_tag().get("permission-probe")
    if probes is not None:
        verdict = "PASS" if probes.passed == probes.count else "FAIL"
        print(f"Breach test (permission-probe): {verdict} "
              f"({probes.passed}/{probes.count} cases held the line)")

    return 0 if report.pass_rate == 1.0 else 1


class _CaseBoundSelector:
    """Adapt :class:`PermissionAwareGrader` (case-aware) to the harness's per-case grader slot.

    ``eval_harness.run`` accepts either one grader or ``Callable[[Case], Grader]``. We return, for
    each case, a tiny grader closure that already knows the case — so the grader can read the
    case's tags to decide present-vs-absent semantics.
    """

    def __init__(self, grader: PermissionAwareGrader, cases) -> None:
        self._grader = grader
        self._by_input_id = {id(c.input): c for c in cases}

    def __call__(self, case: Case):
        grader = self._grader

        class _Bound:
            def grade(self, expected: Any, actual: Any) -> GradeResult:  # noqa: ARG002
                return grader.grade_case(case, actual)

        return _Bound()


if __name__ == "__main__":
    raise SystemExit(main())
