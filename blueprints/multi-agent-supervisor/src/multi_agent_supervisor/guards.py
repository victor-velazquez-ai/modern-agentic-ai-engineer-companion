"""Coordination guards: the things that keep a multi-agent run from melting down.

A supervisor that delegates can fail in three classic ways:

1. **It never stops.** A planner keeps emitting sub-tasks, or re-plans forever. Cap
   the number of orchestration rounds (:class:`IterationGuard`).
2. **It recurses too deep.** A worker that is itself a supervisor spawns sub-teams
   without bound. Cap the delegation depth (:class:`DepthGuard`).
3. **One worker crashes and takes the run with it.** Isolate worker failures so the
   team *degrades* instead of throwing (:func:`run_isolated`).

These are small on purpose. The whole value of the supervisor pattern is that the
control flow is *legible* — you can read exactly when and why it halts.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class GuardTripped(RuntimeError):
    """Raised when an orchestration limit is exceeded. Carries the limit for logs."""

    def __init__(self, kind: str, limit: int) -> None:
        super().__init__(f"{kind} guard tripped (limit={limit})")
        self.kind = kind
        self.limit = limit


@dataclass
class IterationGuard:
    """Caps how many planning/delegation rounds the supervisor may run.

    ``tick()`` once per round; it raises :class:`GuardTripped` when the budget is
    spent. Default of 8 is generous for the demo team but finite — a runaway planner
    halts loudly rather than billing forever.
    """

    max_iterations: int = 8
    count: int = 0

    def tick(self) -> int:
        self.count += 1
        if self.count > self.max_iterations:
            raise GuardTripped("iteration", self.max_iterations)
        return self.count

    @property
    def remaining(self) -> int:
        return max(0, self.max_iterations - self.count)


@dataclass
class DepthGuard:
    """Caps delegation recursion depth (supervisor-of-supervisors).

    Use :meth:`descend` to get a child guard one level deeper; it raises before the
    child is created once the cap is hit, so the recursion can never exceed it.
    """

    max_depth: int = 3
    depth: int = 0

    def descend(self) -> "DepthGuard":
        if self.depth + 1 > self.max_depth:
            raise GuardTripped("depth", self.max_depth)
        return DepthGuard(max_depth=self.max_depth, depth=self.depth + 1)


@dataclass
class Outcome(Generic[T]):
    """The result of an isolated unit of work: either a value or a captured failure.

    Crucially, a failed :class:`Outcome` is *data*, not an exception in flight. The
    supervisor can look at ``ok`` across all workers and decide how to degrade.
    """

    ok: bool
    value: T | None = None
    error: str | None = None
    traceback_str: str | None = None

    @property
    def failed(self) -> bool:
        return not self.ok

    def unwrap(self) -> T:
        if not self.ok:
            raise RuntimeError(f"unwrap() on a failed Outcome: {self.error}")
        # mypy: value is present whenever ok is True by construction.
        return self.value  # type: ignore[return-value]


def run_isolated(fn: Callable[[], T]) -> Outcome[T]:
    """Run ``fn`` and capture any exception as an :class:`Outcome` instead of raising.

    This is the failure-isolation primitive: one worker blowing up becomes a recorded
    failure the supervisor can route around, not a crash that aborts the whole team.
    """
    try:
        return Outcome(ok=True, value=fn())
    except Exception as exc:  # noqa: BLE001 — isolation is the whole point here.
        return Outcome(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            traceback_str=traceback.format_exc(),
        )
