"""Runner — aggregation, per-tag breakdown, per-case grading, and error isolation."""

from __future__ import annotations

import pytest

from eval_harness.dataset import Case
from eval_harness.graders.base import GradeResult
from eval_harness.graders.deterministic import Contains, ExactMatch, JSONSchemaMatch
from eval_harness.runner import run, run_grouped


def _case(cid: str, inp, exp, *tags: str) -> Case:
    return Case(id=cid, input=inp, expected=exp, tags=tuple(tags))


CASES = [
    _case("a", "q-a", "Paris", "exact", "geo"),
    _case("b", "q-b", "Tokyo", "exact", "geo"),
    _case("c", "q-c", "Lyon", "exact", "geo"),
]


def perfect_agent(_inp: str) -> str:
    return {"q-a": "Paris", "q-b": "Tokyo", "q-c": "Lyon"}[_inp]


def half_agent(inp: str) -> str:
    # Right on a and b, wrong on c.
    return {"q-a": "Paris", "q-b": "Tokyo"}.get(inp, "WRONG")


def test_run_all_pass() -> None:
    report = run(perfect_agent, CASES, ExactMatch())
    assert report.total == 3
    assert report.passed == 3
    assert report.mean_score == 1.0
    assert report.pass_rate == 1.0
    assert report.failures == ()


def test_run_some_fail() -> None:
    report = run(half_agent, CASES, ExactMatch())
    assert report.passed == 2
    assert report.mean_score == pytest.approx(2 / 3)
    failed_ids = {r.case_id for r in report.failures}
    assert failed_ids == {"c"}


def test_per_tag_breakdown() -> None:
    mixed = [
        _case("x1", "x1", "yes", "capability-x"),
        _case("x2", "x2", "yes", "capability-x"),
        _case("y1", "y1", "yes", "capability-y"),
    ]

    def agent(inp: str) -> str:
        return "yes" if inp != "x2" else "no"  # x2 fails

    report = run(agent, mixed, ExactMatch())
    by_tag = report.by_tag()
    assert by_tag["capability-x"].mean_score == 0.5
    assert by_tag["capability-x"].passed == 1
    assert by_tag["capability-x"].count == 2
    assert by_tag["capability-y"].mean_score == 1.0
    # tag_scores is the slice the gate diffs.
    assert report.tag_scores()["capability-y"] == 1.0


def test_case_in_multiple_tags_counts_in_each() -> None:
    cases = [_case("m", "m", "ok", "tag-a", "tag-b")]
    report = run(lambda _i: "ok", cases, ExactMatch())
    by_tag = report.by_tag()
    assert by_tag["tag-a"].count == 1
    assert by_tag["tag-b"].count == 1


def test_candidate_exception_is_isolated_not_raised() -> None:
    def explodes(_inp: str) -> str:
        raise RuntimeError("boom")

    report = run(explodes, CASES, ExactMatch())
    assert report.passed == 0
    assert all(r.score == 0.0 for r in report.results)
    assert "candidate raised" in report.results[0].rationale


def test_threshold_controls_pass_boundary() -> None:
    # A grader that always returns 0.6; pass at 0.5, fail at 0.7.
    class Sixty:
        def grade(self, expected, actual) -> GradeResult:  # noqa: ANN001
            return GradeResult(0.6, "fixed")

    lenient = run(perfect_agent, CASES, Sixty(), threshold=0.5)
    strict = run(perfect_agent, CASES, Sixty(), threshold=0.7)
    assert lenient.passed == 3
    assert strict.passed == 0
    # mean score is independent of the threshold.
    assert lenient.mean_score == strict.mean_score == pytest.approx(0.6)


def test_per_case_grader_selector() -> None:
    cases = [
        _case("e", "e", "Paris", "exact"),
        _case("c", "c", "alpha beta", "contains"),
    ]

    def select(case: Case):
        return Contains() if "contains" in case.tags else ExactMatch()

    def agent(inp: str) -> str:
        return {"e": "Paris", "c": "here is alpha beta yes"}[inp]

    report = run(agent, cases, select)
    assert report.passed == 2


def test_run_grouped_routes_by_first_matching_tag() -> None:
    cases = [
        _case("ex", "ex", "Paris", "exact"),
        _case("js", "js", {"type": "object", "required": ["k"]}, "json"),
    ]
    graders = {"exact": ExactMatch(), "json": JSONSchemaMatch()}

    def agent(inp: str):
        return "Paris" if inp == "ex" else {"k": 1}

    report = run_grouped(agent, cases, graders, default=ExactMatch())
    assert report.passed == 2


def test_report_to_dict_is_json_shaped() -> None:
    report = run(half_agent, CASES, ExactMatch())
    d = report.to_dict()
    assert set(d) >= {"mean_score", "pass_rate", "total", "passed", "tag_scores"}
    assert isinstance(d["tag_scores"], dict)
    assert d["total"] == 3


def test_report_render_contains_breakdown_and_failures() -> None:
    text = run(half_agent, CASES, ExactMatch()).render()
    assert "Per-tag breakdown" in text
    assert "Failures" in text
    assert "c" in text


def test_empty_report_is_safe() -> None:
    from eval_harness.runner import Report

    empty = Report(results=())
    assert empty.mean_score == 0.0
    assert empty.pass_rate == 0.0
    assert empty.by_tag() == {}
