"""handlers — a second module, so the migration spans more than one file.

It imports the deprecated ``legacy_clean`` and uses it once. ``app/migrate.py`` must rewrite
*this* call site too, proving the per-file manifest really walks the whole repo (not just the
file the bug lives in).
"""

from __future__ import annotations

from textkit import legacy_clean


def handle(payload: str) -> str:
    """Clean an incoming payload before storing it. A deprecated-API call site."""
    return legacy_clean(payload)
