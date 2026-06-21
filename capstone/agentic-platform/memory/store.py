"""``MemoryStore`` — the one surface an agent reads from and writes to (Ch 14).

The agent should not care that memory has layers. It wants four verbs:

* :meth:`MemoryStore.remember` — write a turn into the working window (auto-compacts on overflow).
* :meth:`MemoryStore.memorize` — promote a durable fact/episode into long-term memory.
* :meth:`MemoryStore.recall` — read relevant long-term records for the current query.
* :meth:`MemoryStore.context` — render the live window (system + summary + recent turns) to send.

Persistence is a policy of the store, not the agent's problem: :meth:`save` snapshots both layers
through the injected backend, and :meth:`open`/:meth:`load` restore them — so state survives a
turn, a session, and (with the SQLite/Postgres backend) a process restart. For *run-level*
resume-after-crash, see :mod:`memory.checkpoint`, which snapshots this same state under a run id.

Everything defaults to MOCK: the in-process backend and the offline summarizer, so a fresh
``MemoryStore()`` runs free with no keys and no files.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .backends.base import PersistenceBackend, StoreState
from .backends.memory import InMemoryBackend
from .longterm import LongTermMemory, MemoryRecord
from .summarize import Summarizer, default_summarizer
from .working import Message, Role, WorkingMemory


@dataclass
class MemoryStore:
    """Facade composing working memory, long-term memory, and a persistence backend."""

    session_id: str = "default"
    token_budget: int = 512
    keep_last: int = 2
    backend: PersistenceBackend | None = None
    summarizer: Summarizer | None = None

    working: WorkingMemory = None  # type: ignore[assignment]  # set in __post_init__
    longterm: LongTermMemory = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.backend is None:
            self.backend = InMemoryBackend()
        if self.summarizer is None:
            # honors COMPANION_MOCK; mock by default (no spend)
            self.summarizer = default_summarizer()
        self.working = WorkingMemory(
            token_budget=self.token_budget,
            keep_last=self.keep_last,
            summarizer=self.summarizer,
        )
        self.longterm = LongTermMemory()
        # if this session already exists in the backend, pick up where we left off
        self.load()

    # -- working memory -------------------------------------------------------------------------

    def remember(self, role: Role, content: str) -> None:
        """Add a conversation turn to the working window (compacts if it overflows)."""
        self.working.add(role, content)

    def set_system(self, content: str) -> None:
        """Set the always-retained system prompt."""
        self.working.add("system", content)

    def context(self) -> list[Message]:
        """The live window as the model should receive it."""
        return self.working.render()

    @property
    def summary(self) -> str:
        """The current rolling summary of evicted turns (empty until first compaction)."""
        return self.working.rolling_summary

    # -- long-term memory -----------------------------------------------------------------------

    def memorize(
        self, text: str, *, kind: str = "fact", tags: Iterable[str] = ()
    ) -> MemoryRecord:
        """Promote a durable fact/episode into long-term memory."""
        return self.longterm.add(text, kind=kind, tags=tags)

    def recall(
        self,
        query: str,
        *,
        top_k: int = 3,
        kind: str | None = None,
        min_score: float = 0.0,
    ) -> list[MemoryRecord]:
        """Retrieve the most relevant long-term records for ``query``."""
        return self.longterm.search(query, top_k=top_k, kind=kind, min_score=min_score)

    # -- persistence ----------------------------------------------------------------------------

    def state(self) -> StoreState:
        """The full serializable state of both layers (also used by the checkpoint layer)."""
        return StoreState(
            working=self.working.snapshot(),
            longterm=self.longterm.snapshot(),
        )

    def restore(self, state: StoreState) -> None:
        """Replace both layers from a previously captured :class:`StoreState`."""
        self.working.restore(state["working"])
        self.longterm.restore(state["longterm"])

    def save(self) -> None:
        """Persist both layers for this session through the backend."""
        assert self.backend is not None
        self.backend.save(self.session_id, self.state())

    def load(self) -> bool:
        """Restore both layers for this session if the backend has them. Returns True if loaded."""
        assert self.backend is not None
        state = self.backend.load(self.session_id)
        if state is None:
            return False
        self.restore(state)
        return True

    def close(self) -> None:
        """Release backend resources (does not auto-save — call :meth:`save` first)."""
        assert self.backend is not None
        self.backend.close()

    # -- ergonomics -----------------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        session_id: str,
        backend: PersistenceBackend,
        *,
        token_budget: int = 512,
        keep_last: int = 2,
        summarizer: Summarizer | None = None,
    ) -> "MemoryStore":
        """Open (and restore, if present) a session on a specific backend.

        This is the path the demo uses to simulate a restart: build a *new* store against the same
        durable backend and watch it recall what an earlier store wrote.
        """
        return cls(
            session_id=session_id,
            backend=backend,
            token_budget=token_budget,
            keep_last=keep_last,
            summarizer=summarizer,
        )

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
