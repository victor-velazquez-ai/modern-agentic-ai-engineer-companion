"""File-backed persistence via SQLite — durability across a real restart.

This is the example that proves the persistence seam: write a session, *close the store*, reopen a
fresh store pointing at the same file, and the state is still there. SQLite ships with the Python
stdlib (``sqlite3``), so this adds **no dependency** — exactly what a standalone blueprint wants.

**Production swap.** In a real service you would point the same :class:`PersistenceBackend`
interface at Postgres (``psycopg`` is already in ``requirements.txt``) for concurrency and
durability across instances, or Redis for hot session state. The schema below — one row per
session holding a JSON blob — maps directly to a ``jsonb`` column in Postgres. The store above does
not change.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .base import StoreState


class SQLiteBackend:
    """Persist session state as JSON in a single-file SQLite database.

    Parameters
    ----------
    path:
        Filesystem path to the database file. Use ``":memory:"`` for an ephemeral DB (tests), or a
        real path for cross-restart durability. Parent directories are created if missing.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False keeps the demo simple; a server would use a connection pool.
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_sessions (
                session_id TEXT PRIMARY KEY,
                state      TEXT NOT NULL,
                updated_at REAL NOT NULL DEFAULT (strftime('%s','now'))
            )
            """
        )
        self._conn.commit()

    def save(self, session_id: str, state: StoreState) -> None:
        payload = json.dumps(state, ensure_ascii=False)
        self._conn.execute(
            """
            INSERT INTO memory_sessions (session_id, state, updated_at)
            VALUES (?, ?, strftime('%s','now'))
            ON CONFLICT(session_id) DO UPDATE SET
                state = excluded.state,
                updated_at = excluded.updated_at
            """,
            (session_id, payload),
        )
        self._conn.commit()

    def load(self, session_id: str) -> StoreState | None:
        cur = self._conn.execute(
            "SELECT state FROM memory_sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def sessions(self) -> list[str]:
        cur = self._conn.execute("SELECT session_id FROM memory_sessions ORDER BY updated_at")
        return [r[0] for r in cur.fetchall()]

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            # already closed — closing twice is fine
            pass

    def __enter__(self) -> "SQLiteBackend":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
