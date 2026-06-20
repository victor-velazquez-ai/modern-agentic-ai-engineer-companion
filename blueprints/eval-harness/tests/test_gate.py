"""Gate — regression past the threshold yields the failure exit code; baseline round-trips."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval_harness.dataset import Case
from eval_harness.gate import (
    EXIT_OK,
    EXIT_REGRESSION,
    EXIT_USAGE,
    gate,
    load_baseline,
    main,
    save_baseline,
)
from eval_harness.graders.deterministic import ExactMatch
from eval_harness.runner import Report, run


def _case(cid: str, inp, exp, *tags: str) -> Case:
    return Case(id=cid, input=inp, expected=exp, tags=tuple(tags))


CASES = [
    _case("a", "a", "yes", "core"),
    _case("b", "b", "yes", "core"),
    _case("c", "c", "yes", "safety"),
    _case("d", "d", "yes", "safety"),
]


def agent_all_good(_inp: str) -> str:
    return "yes"


def agent_safety_regressed(inp: str) -> str:
    # Fails both safety cases (c, d); core still passes.
    return "yes" if inp in ("a", "b") else "no"


def _baseline_report() -> Report:
    return run(agent_all_good, CASES, ExactMatch())


def test_no_regression_passes() -> None:
    base = _baseline_report()
    result = gate(_baseline_report(), base.to_dict(), tolerance=0.02)
    assert result.passed
    assert result.exit_code == EXIT_OK
    assert result.regressions == ()


def test_overall_regression_fails_with_exit_1() -> None:
    base = _baseline_report().to_dict()
    regressed = run(agent_safety_regressed, CASES, ExactMatch())
    result = gate(regressed, base, tolerance=0.02)
    assert not result.passed
    assert result.exit_code == EXIT_REGRESSION
    scopes = {r.scope for r in result.regressions}
    assert "overall" in scopes


def test_per_tag_regression_is_detected() -> None:
    base = _baseline_report().to_dict()
    regressed = run(agent_safety_regressed, CASES, ExactMatch())
    result = gate(regressed, base, tolerance=0.02)
    scopes = {r.scope for r in result.regressions}
    assert "safety" in scopes      # the tanked segment
    assert "core" not in scopes    # untouched segment must not be flagged


def test_per_tag_regression_caught_even_when_overall_within_tolerance() -> None:
    # 10 core cases (stay perfect) + 1 safety case (regresses). The overall mean barely
    # moves, but the per-tag check must still fire — that's the whole point of by-tag gating.
    cases = [_case(f"c{i}", f"c{i}", "yes", "core") for i in range(10)]
    cases.append(_case("s0", "s0", "yes", "safety"))

    base = run(lambda _i: "yes", cases, ExactMatch()).to_dict()

    def regress_safety(inp: str) -> str:
        return "no" if inp == "s0" else "yes"

    new = run(regress_safety, cases, ExactMatch())
    # Overall dropped by ~1/11 = 0.09; with a generous overall tolerance the per-tag check
    # is what guarantees we still catch the safety regression.
    overall_only = gate(new, base, tolerance=0.5, check_tags=False)
    assert overall_only.passed  # overall slips past a loose tolerance
    with_tags = gate(new, base, tolerance=0.5, check_tags=True)
    assert not with_tags.passed
    assert {r.scope for r in with_tags.regressions} == {"safety"}


def test_tolerance_absorbs_small_dips() -> None:
    base = {"mean_score": 1.0, "tag_scores": {"core": 1.0}}

    class NearlyPerfect:
        def grade(self, expected, actual):  # noqa: ANN001, ANN201
            from eval_harness.graders.base import GradeResult

            return GradeResult(0.99, "close")

    report = run(agent_all_good, CASES, NearlyPerfect())
    # 0.99 vs baseline 1.0 -> drop 0.01, inside a 0.02 tolerance -> pass.
    assert gate(report, base, tolerance=0.02).passed
    # ...but a 0.005 tolerance flags it.
    assert not gate(report, base, tolerance=0.005).passed


def test_new_tag_is_not_a_regression() -> None:
    base = {"mean_score": 0.0, "tag_scores": {"old": 1.0}}
    # Current run has a brand-new tag and no "old" tag at all.
    cases = [_case("n", "n", "yes", "brand-new")]
    report = run(agent_all_good, cases, ExactMatch())
    result = gate(report, base, tolerance=0.02)
    assert result.passed  # adding cases/tags never trips the gate


def test_baseline_save_load_roundtrip(tmp_path: Path) -> None:
    report = _baseline_report()
    path = tmp_path / "baseline.json"
    save_baseline(report, path)
    assert path.exists()
    loaded = load_baseline(path)
    assert loaded["mean_score"] == pytest.approx(report.mean_score)
    assert "safety" in loaded["tag_scores"]
    # A gate against the just-saved baseline trivially passes.
    assert gate(report, loaded, tolerance=0.0).passed


def test_load_baseline_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_baseline(tmp_path / "nope.json")


# --- CLI entrypoint (exit-code contract) -----------------------------------------------

def test_cli_update_then_pass_then_regression(tmp_path: Path, capsys) -> None:
    # Build a dataset whose `expected` == `input` so the echo candidate scores 1.0.
    ds = tmp_path / "ds.jsonl"
    ds.write_text(
        '{"id": "1", "input": "x", "expected": "x", "tags": ["t"]}\n'
        '{"id": "2", "input": "y", "expected": "y", "tags": ["t"]}\n',
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"

    # 1) --update writes the baseline and exits 0.
    code = main([str(ds), "--baseline", str(baseline), "--update"])
    assert code == EXIT_OK
    assert baseline.exists()

    # 2) Same dataset vs baseline -> no regression -> exit 0.
    assert main([str(ds), "--baseline", str(baseline)]) == EXIT_OK

    # 3) Regress the dataset (expected no longer equals input) -> exit 1.
    ds.write_text(
        '{"id": "1", "input": "x", "expected": "DIFFERENT", "tags": ["t"]}\n'
        '{"id": "2", "input": "y", "expected": "y", "tags": ["t"]}\n',
        encoding="utf-8",
    )
    assert main([str(ds), "--baseline", str(baseline)]) == EXIT_REGRESSION


def test_cli_missing_baseline_is_usage_error(tmp_path: Path) -> None:
    ds = tmp_path / "ds.jsonl"
    ds.write_text('{"id": "1", "input": "x", "expected": "x", "tags": ["t"]}\n', encoding="utf-8")
    assert main([str(ds), "--baseline", str(tmp_path / "absent.json")]) == EXIT_USAGE
