"""CI guard for the dataset schema (see ../SCHEMA.md).

Every row in every ``datasets/*.jsonl`` file must:
  - be valid JSON on a single line,
  - have a unique, non-empty ``id``,
  - carry the required fields (``id``, ``input``, ``expected``, ``tags``),
  - carry at least one tag,
  - contain no obvious secrets (a cheap PII/secret smell-test).

Run it with:  pytest tests/        (or `make test`)

This file is the enforcement half of SCHEMA.md — if you change the schema,
update both. It contains NO business logic; it only validates the data contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"

REQUIRED_FIELDS = ("id", "input", "expected", "tags")

# Cheap "does this look like a leaked secret?" patterns. Not exhaustive — a
# tripwire, not a vault. TODO: extend for your org's key formats.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),           # OpenAI-style key
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),     # Anthropic-style key
    re.compile(r"AKIA[0-9A-Z]{16}"),              # AWS access key id
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _iter_rows():
    """Yield (path, lineno, raw_line) for every non-blank dataset line."""
    files = sorted(DATASETS_DIR.glob("*.jsonl"))
    assert files, f"No *.jsonl datasets found under {DATASETS_DIR}"
    for path in files:
        with path.open(encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                if raw.strip():
                    yield path, lineno, raw


def _all_rows():
    return list(_iter_rows())


def _row_id(path: Path, lineno: int, raw: str) -> str:
    return f"{path.name}:{lineno}"


ROWS = _all_rows()
ROW_IDS = [_row_id(*r) for r in ROWS]


@pytest.mark.parametrize("path,lineno,raw", ROWS, ids=ROW_IDS)
def test_row_is_valid_json(path, lineno, raw):
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"{path}:{lineno}: not valid JSON — {exc}")


@pytest.mark.parametrize("path,lineno,raw", ROWS, ids=ROW_IDS)
def test_required_fields_present(path, lineno, raw):
    row = json.loads(raw)
    missing = [f for f in REQUIRED_FIELDS if f not in row]
    assert not missing, f"{path}:{lineno}: missing field(s): {missing}"


@pytest.mark.parametrize("path,lineno,raw", ROWS, ids=ROW_IDS)
def test_id_is_non_empty_string(path, lineno, raw):
    row = json.loads(raw)
    assert isinstance(row.get("id"), str) and row["id"].strip(), (
        f"{path}:{lineno}: 'id' must be a non-empty string"
    )


@pytest.mark.parametrize("path,lineno,raw", ROWS, ids=ROW_IDS)
def test_has_at_least_one_tag(path, lineno, raw):
    row = json.loads(raw)
    tags = row.get("tags")
    assert isinstance(tags, list) and len(tags) >= 1, (
        f"{path}:{lineno}: 'tags' must be a list with at least one tag"
    )
    assert all(isinstance(t, str) and t.strip() for t in tags), (
        f"{path}:{lineno}: every tag must be a non-empty string"
    )


@pytest.mark.parametrize("path,lineno,raw", ROWS, ids=ROW_IDS)
def test_no_obvious_secrets(path, lineno, raw):
    for pat in SECRET_PATTERNS:
        assert not pat.search(raw), (
            f"{path}:{lineno}: possible secret/PII matching /{pat.pattern}/ — "
            "datasets are committed; never include real keys or PII."
        )


def test_ids_are_unique():
    seen: dict[str, str] = {}
    for path, lineno, raw in ROWS:
        row = json.loads(raw)
        case_id = row.get("id")
        if case_id in seen:
            pytest.fail(
                f"Duplicate id {case_id!r}: {seen[case_id]} and {path.name}:{lineno}"
            )
        seen[case_id] = f"{path.name}:{lineno}"
