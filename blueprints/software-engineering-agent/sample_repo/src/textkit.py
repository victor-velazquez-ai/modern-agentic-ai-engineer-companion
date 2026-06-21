"""textkit — a tiny string library that stands in for the team's codebase.

It carries exactly the two things the agent works on:

* ``slugify`` has a **bug** (it forgets the separator), and a red test pins it. This is the
  code-review / fix-generation target.
* ``legacy_clean`` is **deprecated** in favour of ``normalize``; call sites below still use the
  old name. This is the framework-migration target.

Keep it small and dependency-free: the oracle imports and runs it in-process, so the whole
demo stays offline and fast.
"""

from __future__ import annotations

import re

_NON_WORD = re.compile(r"[^a-z0-9]+")


def slugify(text: str, sep: str = "-") -> str:
    """Turn arbitrary text into a URL slug.

    BUG (on purpose): the words are joined with ``""`` instead of ``sep``, so
    ``slugify("Hello World")`` returns ``"helloworld"``. ``tests/test_slugify.py`` is red until
    the agent fixes the join. The fix is a single token — ``"".join`` → ``sep.join`` — which is
    exactly the kind of mechanical change the verification loop can prove correct.
    """
    words = _NON_WORD.sub(" ", text.lower()).split()
    return "".join(words)  # <-- bug: should be ``sep.join(words)``


def normalize(text: str) -> str:
    """Collapse whitespace and trim — the *new* canonical cleaner.

    ``legacy_clean`` is kept only as a deprecated alias; new code should call this.
    """
    return " ".join(text.split())


def legacy_clean(text: str) -> str:
    """DEPRECATED: use :func:`normalize`. Migration target for ``app/migrate.py``."""
    return normalize(text)


# --- internal call sites that still use the deprecated API (migration targets) -------------

def title_case(text: str) -> str:
    """Title-case cleaned text. Uses the deprecated cleaner — a migration call site."""
    return legacy_clean(text).title()


def shout(text: str) -> str:
    """Upper-case cleaned text. Uses the deprecated cleaner — a migration call site."""
    return legacy_clean(text).upper()
