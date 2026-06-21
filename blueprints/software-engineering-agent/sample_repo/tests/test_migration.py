"""Behaviour the migration must preserve.

The deprecated ``legacy_clean`` and the new ``normalize`` are exact aliases, so the migration
is a *pure rename*: these tests must stay green before and after ``app/migrate.py`` rewrites the
call sites. They are the oracle's proof that the migration changed the spelling, not the
behaviour.
"""

from textkit import normalize, shout, title_case


def test_normalize_collapses_whitespace() -> None:
    assert normalize("  a   b ") == "a b"


def test_title_case_still_works() -> None:
    assert title_case("  hello   world ") == "Hello World"


def test_shout_still_works() -> None:
    assert shout(" hi  there ") == "HI THERE"
