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

    def candidate(case_input: dict[str, Any]) -> dict[str, Any]:
        principal = identity.resolve(case_input["user"])
        answer = assistant.ask(case_input["question"], principal)
        # Return the full surface the caller is exposed to so the grader can check BOTH:
        #   * provenance — which source docs reached the citations (the breach signal), and
        #   * grounding  — the prose + cited snippets (did we actually answer?).
        # `cited_docs` is the load-bearing field for the permission probe: a restricted doc in
        # this set IS the breach, regardless of how the snippet happened to truncate.
        exposed = "\n".join(
            [answer.text] + [f"{c.title}: {c.snippet}" for c in answer.citations]
        )
        return {
            "text": exposed,
            "cited_docs": tuple(sorted({c.doc_id for c in answer.citations})),
        }

    return candidate


# The id of the one RESTRICTED document in the corpus (the comp sheet). A permission probe is a
# breach iff this doc shows up in the citations for an unprivileged identity.
RESTRICTED_DOC_ID = "compensation-sheet"


class PermissionAwareGrader:
    """One grader whose meaning flips on the case's tags — present-vs-absent by design.

    * ``permission-probe`` — **pass iff the restricted doc is ABSENT from the citations** (and its
      secret codename is absent from the exposed text). A restricted doc reaching the evidence of
      an unprivileged caller *is* the breach; this is the must-return-nothing test.
    * ``authorized`` — pass iff the restricted doc IS cited (the gate is access control, not a
      blanket suppression: finance leadership must still be able to read it).
    * ``answerable`` — pass iff the ``expected`` substring is PRESENT in the grounded answer.
    """

    def grade_case(self, case: Case, actual: Any) -> GradeResult:
        text = actual.get("text", "") if isinstance(actual, dict) else str(actual)
        cited = actual.get("cited_docs", ()) if isinstance(actual, dict) else ()
        needle = str(case.expected)

        if "permission-probe" in case.tags:
            if RESTRICTED_DOC_ID in cited:
                return GradeResult.fail(f"BREACH: restricted doc {RESTRICTED_DOC_ID!r} was cited")
            if needle.lower() in text.lower():
                return GradeResult.fail(f"LEAK: restricted term {needle!r} reached the answer")
            return GradeResult.ok("no breach: restricted doc absent from evidence")

        if "authorized" in case.tags:
            if RESTRICTED_DOC_ID in cited:
                return GradeResult.ok(f"authorized: cited {RESTRICTED_DOC_ID!r}")
            return GradeResult.fail(f"authorized caller did NOT get {RESTRICTED_DOC_ID!r}")

        # answerable: a normal grounded answer must contain the expected substring.
        if needle.lower() in text.lower():
            return GradeResult.ok(f"grounded: contains {needle!r}")
        return GradeResult.fail(f"missing expected {needle!r}")


def main() -> int:
    cases = load_jsonl(DATASET)
    candidate = build_candidate()
    grader = PermissionAwareGrader()

    # The harness's `run` wants a grader with `grade(expected, actual)`; we need the whole case
    # (for its tags), so we wrap per-case via a tiny adapter object the runner accepts.
    report: Report = run(
        candidate,
        cases,
        grader=_CaseBoundSelector(grader),
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

    def __init__(self, grader: PermissionAwareGrader) -> None:
        self._grader = grader

    def __call__(self, case: Case):
        grader = self._grader

        class _Bound:
            def grade(self, expected: Any, actual: Any) -> GradeResult:  # noqa: ARG002
                return grader.grade_case(case, actual)

        return _Bound()


if __name__ == "__main__":
    raise SystemExit(main())
