"""Execute a verified query — read-only, row-limited, timeout-guarded (Ch 12, 40, 41).

The execution tool. By the time SQL reaches here it has already passed :mod:`app.verify`, but
this layer assumes nothing and enforces the safety contract *at the connection*, because the
right place to be safe is every place (Ch 41, defense in depth):

* **Read-only connection.** Opened with SQLite's ``mode=ro`` immutable URI and an authorizer that
  rejects any non-read operation, so even a query that somehow slipped past verify cannot write.
* **Row cap.** ``fetchmany(max_rows)`` — never materialize an unbounded result; a careless question
  cannot pull the whole table into memory.
* **Timeout / interrupt guard.** A wall-clock budget via ``set_progress_handler`` interrupts a
  runaway scan, the cheap stand-in for a warehouse statement timeout.

To point this at a real warehouse, replace :func:`connect_readonly` with your engine's read-only,
row-limited, timeout-guarded connection — *the rest of the copilot does not change* (PLAN: "point
``app/run.py`` at your warehouse with read-only, row-limited, timeout-guarded credentials").
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "warehouse.sqlite"
DEFAULT_MAX_ROWS = 1000
DEFAULT_TIMEOUT_S = 5.0


class ExecutionError(RuntimeError):
    """Raised when execution is refused or fails (a clean, model/human-readable message)."""


@dataclass(frozen=True)
class QueryResult:
    """The outcome of running a query: columns, rows, and whether the cap truncated it."""

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    truncated: bool = False
    elapsed_ms: float = 0.0

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def render(self, max_rows: int = 20) -> str:
        """A compact text table for the console / the 'show me the answer' affordance."""
        if not self.columns:
            return "(no columns)"
        head = " | ".join(self.columns)
        sep = "-" * len(head)
        body = [
            " | ".join("" if v is None else str(v) for v in row)
            for row in self.rows[:max_rows]
        ]
        more = f"\n... (+{self.row_count - max_rows} more rows)" if self.row_count > max_rows else ""
        trunc = "  [truncated at row cap]" if self.truncated else ""
        return f"{head}\n{sep}\n" + "\n".join(body) + more + trunc


def connect_readonly(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open a strictly read-only SQLite connection (immutable URI + an authorizer).

    The authorizer is the belt to the URI's braces: it denies every SQLite action except the
    handful a read query needs (SELECT, READ, function calls), so a write can't happen even if a
    statement slipped through verification.
    """
    p = Path(db_path)
    if not p.exists():
        raise ExecutionError(
            f"warehouse not found: {p}. Build the bundled mock with "
            f"`python data/build_warehouse.py` first."
        )
    uri = f"file:{p.as_posix()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.set_authorizer(_read_only_authorizer)
    return conn


def _read_only_authorizer(action: int, *_args) -> int:
    """SQLite authorizer callback: allow only read actions, deny everything else."""
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        getattr(sqlite3, "SQLITE_RECURSIVE", 33),
    }
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def run_query(
    sql: str,
    *,
    db_path: str | Path = DEFAULT_DB,
    max_rows: int = DEFAULT_MAX_ROWS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> QueryResult:
    """Execute ``sql`` read-only, capping rows and interrupting on a time budget.

    Raises :class:`ExecutionError` on any refusal or failure, with a message safe to show a human
    or hand back to the agent loop as a tool error.
    """
    conn = connect_readonly(db_path)
    deadline = time.perf_counter() + max(0.01, timeout_s)

    def _guard() -> int:
        # Returning non-zero from the progress handler interrupts the query (the timeout guard).
        return 1 if time.perf_counter() > deadline else 0

    # Call the guard every N virtual-machine instructions — frequent enough to bound runaways.
    conn.set_progress_handler(_guard, 1000)

    start = time.perf_counter()
    try:
        cur = conn.execute(sql)
        columns = tuple(d[0] for d in cur.description) if cur.description else ()
        fetched = cur.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = tuple(tuple(r) for r in fetched[:max_rows])
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise ExecutionError(f"query exceeded the {timeout_s:.1f}s time budget") from exc
        raise ExecutionError(f"SQL error: {exc}") from exc
    except sqlite3.DatabaseError as exc:
        raise ExecutionError(f"refused by read-only policy: {exc}") from exc
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()

    return QueryResult(
        columns=columns,
        rows=rows,
        truncated=truncated,
        elapsed_ms=(time.perf_counter() - start) * 1000.0,
    )


def warehouse_path() -> Path:
    """The bundled mock warehouse path (env-overridable for a real target)."""
    return Path(os.getenv("TEXT_TO_SQL_DB", str(DEFAULT_DB)))
