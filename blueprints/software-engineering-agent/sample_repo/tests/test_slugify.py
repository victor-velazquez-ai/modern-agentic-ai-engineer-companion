"""The red test that pins the ``slugify`` bug — the oracle's ground truth.

This file is the *test contract*: the agent owns making it pass, you own what it asserts. The
oracle runs these assertions in-process and refuses any candidate that "passes" by weakening
them (see ``ci/oracle.py`` → assertion-deletion guard).

These are plain ``assert``-style functions so the oracle can run them with **no pytest
dependency** — it discovers ``test_*`` callables and calls them. Real repos point the oracle at
their actual ``pytest``/``unittest`` command instead.
"""

from textkit import slugify


def test_slugify_inserts_separator() -> None:
    # RED until the bug is fixed: today slugify returns "helloworld".
    assert slugify("Hello World") == "hello-world"


def test_slugify_respects_custom_separator() -> None:
    assert slugify("Hello World", sep="_") == "hello_world"


def test_slugify_collapses_punctuation() -> None:
    assert slugify("  Hello,   World!! ") == "hello-world"


def test_slugify_single_word_unchanged() -> None:
    # This one passes even with the bug — a guard against a "fix" that breaks the single-word
    # case while making the multi-word case pass.
    assert slugify("Hello") == "hello"
