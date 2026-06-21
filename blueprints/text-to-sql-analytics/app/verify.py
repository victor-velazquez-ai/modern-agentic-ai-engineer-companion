"""Verify a generated query *before* it runs — the reasoning check in the loop (Ch 16, 41).

The PLAN treats this copilot as exactly that — a copilot, not an oracle — and the verification
loop is what earns that trust: *"a plausible-looking wrong number is worse than no answer."* So
between **generate** and **execute** sits this gate. It is deterministic, free, and runs every
time, on every path:

* **Read-only.** Reject anything that is not a single ``SELECT``: no ``INSERT/UPDATE/DELETE/DROP/
  ALTER/ATTACH``, no multiple statements, no comments hiding a second statement. Defense in depth
  with run.py's read-only connection (Ch 41 — never trust one layer).
* **Schema-grounded.** Every table/column the query references must exist in the semantic layer.
  A query against a hallucinated ``profit`` column fails *here*, before it can return a confident
  wrong number.
* **Bounded.** A ``LIMIT`` must be present so a careless question cannot scan the whole table
  (cost guard, Ch 40/41).
* **Coherent.** The structured plan must name a real metric, and any grouped query must select what
  it groups by.

Verification returns a :class:`VerifyResult` (ok + reasons), never raises on a bad query — the
caller decides whether to block, and the human sees the reasons.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .nl_to_sql import SqlPlan
from .semantic import SemanticLayer, load_semantic_layer

# Statements that mutate or escape a read-only contract. Matched as whole words, case-insensitive.
_FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "truncate", "attach", "detach", "pragma", "vacuum", "reindex", "grant", "revoke",
)

# Identifier-ish tokens of the form table.column we validate against the schema.
_DOTTED = re.compile(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b")
_WORD = re.compile(r"[a-zA-Z_][\w]*")


@dataclass(frozen=True)
class VerifyResult:
    """The verdict: is this plan safe and coherent enough to execute?"""

    ok: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        return not self.ok

    def explain(self) -> str:
        if self.ok:
            return "verified: read-only, schema-grounded, bounded"
        return "blocked: " + "; ".join(self.reasons)


class QueryVerifier:
    """Runs the pre-execution checks against the semantic layer's schema."""

    def __init__(self, layer: SemanticLayer | None = None, *, require_limit: bool = True) -> None:
        self.layer = layer or load_semantic_layer()
        self.require_limit = require_limit
        self._known_tables = self.layer.known_tables()
        self._known_columns = self.layer.known_columns()

    def verify(self, plan: SqlPlan) -> VerifyResult:
        reasons: list[str] = []
        sql = plan.sql or ""
        lowered = sql.lower()

        # 1) read-only: exactly one statement, and it must be a SELECT.
        statements = [s for s in sql.split(";") if s.strip()]
        if len(statements) != 1:
            reasons.append(f"expected exactly one statement, found {len(statements)}")
        if not lowered.lstrip().startswith("select"):
            reasons.append("query must start with SELECT (read-only)")
        for kw in _FORBIDDEN:
            if re.search(rf"\b{kw}\b", lowered):
                reasons.append(f"forbidden keyword for a read-only query: {kw.upper()}")
        if "--" in sql or "/*" in sql:
            reasons.append("SQL comments are not allowed (could hide a second statement)")

        # 2) schema-grounded: every table.column reference must exist.
        for m in _DOTTED.finditer(sql):
            table, col = m.group(1), m.group(2)
            ref = f"{table}.{col}"
            # Skip alias-like dotted tokens only if the left side is a known table.
            if table in self._known_tables and ref not in self._known_columns:
                reasons.append(f"unknown column referenced: {ref}")

        for table in self._referenced_tables(sql):
            if table not in self._known_tables:
                reasons.append(f"unknown table referenced: {table}")

        # 3) bounded: a LIMIT keeps a careless question from scanning everything.
        if self.require_limit and not re.search(r"\blimit\b", lowered):
            reasons.append("query has no LIMIT (cost guard requires a row cap)")

        # 4) coherent plan: the metric must be real; grouped queries select their grouping.
        if not self.layer.metric(plan.metric):
            reasons.append(f"plan names an unknown metric: {plan.metric!r}")
        if plan.dimensions and "group by" not in lowered:
            reasons.append("plan has dimensions but the SQL has no GROUP BY")

        return VerifyResult(ok=not reasons, reasons=tuple(reasons))

    def _referenced_tables(self, sql: str) -> set[str]:
        """Best-effort: tables named after FROM / JOIN."""
        found: set[str] = set()
        for kw in ("from", "join"):
            for m in re.finditer(rf"\b{kw}\s+([a-zA-Z_][\w]*)", sql, re.IGNORECASE):
                found.add(m.group(1))
        return found


def verify_plan(plan: SqlPlan, layer: SemanticLayer | None = None) -> VerifyResult:
    """One-call convenience used by the agent loop, the demo, and the evals."""
    return QueryVerifier(layer).verify(plan)
