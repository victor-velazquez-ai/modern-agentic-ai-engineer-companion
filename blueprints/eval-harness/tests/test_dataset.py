"""Dataset loader — schema enforcement and the committed example set parse cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval_harness.dataset import (
    Case,
    DatasetError,
    load_jsonl,
    parse_case,
    tags_of,
)


def test_example_dataset_loads_and_is_tagged(dataset_path: Path) -> None:
    cases = load_jsonl(dataset_path)
    assert len(cases) == 6
    # Every case must carry at least one tag (the standards' CI guard).
    assert all(c.tags for c in cases)
    ids = {c.id for c in cases}
    assert "refuse-credentials" in ids
    # tags_of returns the sorted union.
    tags = tags_of(cases)
    assert "must-refuse" in tags
    assert tags == sorted(tags)


def test_parse_case_minimal() -> None:
    c = parse_case({"id": "x", "input": "in", "expected": "out", "tags": ["t"]})
    assert isinstance(c, Case)
    assert c.id == "x"
    assert c.tags == ("t",)
    assert c.notes == ""


def test_parse_case_requires_fields() -> None:
    with pytest.raises(DatasetError):
        parse_case({"input": "in", "expected": "out", "tags": ["t"]})  # no id
    with pytest.raises(DatasetError):
        parse_case({"id": "x", "expected": "out", "tags": ["t"]})  # no input
    with pytest.raises(DatasetError):
        parse_case({"id": "x", "input": "in", "tags": ["t"]})  # no expected


def test_parse_case_requires_a_tag() -> None:
    with pytest.raises(DatasetError):
        parse_case({"id": "x", "input": "in", "expected": "out", "tags": []})


def test_parse_case_tags_must_be_list() -> None:
    with pytest.raises(DatasetError):
        parse_case({"id": "x", "input": "in", "expected": "out", "tags": "t"})


def test_case_preserves_non_string_payloads() -> None:
    c = parse_case(
        {"id": "j", "input": {"k": 1}, "expected": {"type": "object"}, "tags": ["json"]}
    )
    assert c.input == {"k": 1}
    assert c.expected == {"type": "object"}


def test_load_jsonl_skips_comments_and_blanks(tmp_path: Path) -> None:
    p = tmp_path / "d.jsonl"
    p.write_text(
        "# a comment\n"
        "\n"
        '{"id": "1", "input": "a", "expected": "a", "tags": ["t"]}\n'
        "   \n",
        encoding="utf-8",
    )
    cases = load_jsonl(p)
    assert len(cases) == 1


def test_load_jsonl_rejects_duplicate_ids(tmp_path: Path) -> None:
    p = tmp_path / "dupe.jsonl"
    p.write_text(
        '{"id": "1", "input": "a", "expected": "a", "tags": ["t"]}\n'
        '{"id": "1", "input": "b", "expected": "b", "tags": ["t"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="duplicate"):
        load_jsonl(p)


def test_load_jsonl_reports_bad_json_with_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{not valid json}\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="invalid JSON"):
        load_jsonl(p)


def test_load_jsonl_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_jsonl("does-not-exist.jsonl")


def test_load_jsonl_empty_dataset(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("# only a comment\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="no cases"):
        load_jsonl(p)
