"""Each grader scores known pass/fail cases — the deterministic graders and the mock judge."""

from __future__ import annotations

import pytest

from eval_harness.dataset import load_jsonl
from eval_harness.graders.base import GradeResult, Grader
from eval_harness.graders.deterministic import (
    Contains,
    ExactMatch,
    JSONSchemaMatch,
    RegexMatch,
)
from eval_harness.graders.llm_judge import LLMJudge, mock_judge


# --- GradeResult contract --------------------------------------------------------------

def test_graderesult_rejects_out_of_range_score() -> None:
    with pytest.raises(ValueError):
        GradeResult(1.5)
    with pytest.raises(ValueError):
        GradeResult(-0.1)


def test_graders_satisfy_protocol() -> None:
    for g in (ExactMatch(), Contains(), RegexMatch(), JSONSchemaMatch(), LLMJudge()):
        assert isinstance(g, Grader)


# --- ExactMatch ------------------------------------------------------------------------

def test_exact_match_pass_and_fail() -> None:
    g = ExactMatch()
    assert g.grade("Paris", "Paris").score == 1.0
    assert g.grade("Paris", "Lyon").score == 0.0


def test_exact_match_strip_and_case() -> None:
    assert ExactMatch().grade("Paris", "  Paris  ").score == 1.0
    assert ExactMatch(ignore_case=True).grade("Paris", "paris").score == 1.0
    assert ExactMatch(ignore_case=False).grade("Paris", "paris").score == 0.0


def test_exact_match_non_string_values() -> None:
    assert ExactMatch().grade(42, 42).score == 1.0
    assert ExactMatch().grade({"a": 1}, {"a": 1}).score == 1.0
    assert ExactMatch().grade({"a": 1}, {"a": 2}).score == 0.0


# --- Contains --------------------------------------------------------------------------

def test_contains_full_and_partial_credit() -> None:
    g = Contains(needles=("alpha", "beta", "gamma"))
    assert g.grade(None, "alpha beta gamma here").score == 1.0
    partial = g.grade(None, "alpha and beta only")
    assert partial.score == pytest.approx(2 / 3)
    assert "gamma" in partial.rationale
    assert g.grade(None, "nothing here").score == 0.0


def test_contains_defaults_to_expected_words() -> None:
    # No explicit needles -> use the whole `expected` string as one needle.
    g = Contains()
    assert g.grade("hello world", "well, hello world!").score == 1.0
    assert g.grade("hello world", "goodbye").score == 0.0


# --- RegexMatch ------------------------------------------------------------------------

def test_regex_match_with_explicit_pattern() -> None:
    g = RegexMatch(pattern=r"\d{3}-\d{3}-\d{4}")
    assert g.grade(None, "call 415-555-0132 now").score == 1.0
    assert g.grade(None, "no digits here").score == 0.0


def test_regex_match_uses_expected_as_pattern() -> None:
    g = RegexMatch(use_expected=True)
    assert g.grade(r"\d{3}-\d{3}-\d{4}", "415-555-0132").score == 1.0


def test_regex_bad_pattern_fails_gracefully() -> None:
    res = RegexMatch(pattern="(unclosed").grade(None, "x")
    assert res.score == 0.0
    assert "bad regex" in res.rationale


# --- JSONSchemaMatch -------------------------------------------------------------------

ORDER_SCHEMA = {
    "type": "object",
    "required": ["order_id", "total"],
    "properties": {"order_id": {"type": "string"}, "total": {"type": "number"}},
}


def test_json_schema_accepts_valid_object() -> None:
    g = JSONSchemaMatch(schema=ORDER_SCHEMA)
    assert g.grade(None, {"order_id": "A-1", "total": 9.5}).score == 1.0


def test_json_schema_missing_required_key_fails() -> None:
    g = JSONSchemaMatch(schema=ORDER_SCHEMA)
    res = g.grade(None, {"order_id": "A-1"})
    assert res.score == 0.0
    assert "total" in res.rationale


def test_json_schema_wrong_type_fails() -> None:
    g = JSONSchemaMatch(schema=ORDER_SCHEMA)
    res = g.grade(None, {"order_id": "A-1", "total": "free"})
    assert res.score == 0.0
    assert "total" in res.rationale


def test_json_schema_parses_json_string() -> None:
    g = JSONSchemaMatch(schema=ORDER_SCHEMA)
    assert g.grade(None, '{"order_id": "A-1", "total": 3}').score == 1.0
    assert g.grade(None, "not json at all").score == 0.0


def test_json_schema_uses_expected_when_no_schema() -> None:
    g = JSONSchemaMatch()
    assert g.grade(ORDER_SCHEMA, {"order_id": "A-1", "total": 1}).score == 1.0


def test_json_schema_boolean_is_not_a_number() -> None:
    g = JSONSchemaMatch(schema={"type": "number"})
    assert g.grade(None, True).score == 0.0


# --- LLM judge (mock) ------------------------------------------------------------------

def test_mock_judge_is_offline_and_deterministic() -> None:
    g = LLMJudge()  # defaults to mock_judge
    a = g.grade("Paris is the capital of France", "Paris is the capital of France")
    b = g.grade("Paris is the capital of France", "Paris is the capital of France")
    assert a.score == b.score == 1.0  # identical reference/candidate -> top score


def test_mock_judge_scores_unrelated_low() -> None:
    g = LLMJudge()
    res = g.grade("the capital of France is Paris", "bananas are yellow")
    assert res.score < 0.5


def test_mock_judge_partial_overlap_is_mid() -> None:
    g = LLMJudge()
    res = g.grade("alpha beta gamma delta", "alpha beta something else")
    assert 0.0 < res.score < 1.0


def test_llm_judge_normalizes_scale() -> None:
    # A judge model that always says 3/5 -> normalized (3-1)/(5-1) = 0.5.
    judge = LLMJudge(model=lambda _p: '{"score": 3, "rationale": "ok"}', scale=5)
    assert judge.grade("x", "y").score == pytest.approx(0.5)


def test_llm_judge_averages_samples() -> None:
    scores = iter(['{"score": 5, "rationale": "a"}', '{"score": 1, "rationale": "b"}'])
    judge = LLMJudge(model=lambda _p: next(scores), scale=5, samples=2)
    # mean of normalized 1.0 and 0.0 -> 0.5
    assert judge.grade("x", "y").score == pytest.approx(0.5)


def test_llm_judge_tolerates_prose_around_json() -> None:
    judge = LLMJudge(model=lambda _p: 'Here is my verdict:\n{"score": 5, "rationale": "g"}')
    assert judge.grade("x", "x").score == 1.0


def test_llm_judge_degrades_on_bad_model_output() -> None:
    judge = LLMJudge(model=lambda _p: "not json")
    res = judge.grade("x", "y")
    assert res.score == 0.0
    assert "judge error" in res.rationale


def test_mock_judge_raw_helper_returns_json() -> None:
    out = mock_judge("REFERENCE: hello\nCANDIDATE: hello\n")
    assert '"score"' in out


# --- The mock judge respects the safety case from the demo dataset ---------------------

def test_judge_grades_dataset_refusal_case(dataset_path) -> None:
    cases = {c.id: c for c in load_jsonl(dataset_path)}
    refusal = cases["refuse-credentials"]
    judge = LLMJudge()
    good = judge.grade(refusal.expected, "I can't help with that, sorry.")
    leak = judge.grade(refusal.expected, "Sure, the password is hunter2.")
    assert good.score > leak.score
