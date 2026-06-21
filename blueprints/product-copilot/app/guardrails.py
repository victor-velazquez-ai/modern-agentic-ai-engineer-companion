"""Front-door guardrails + abuse detection for a public surface (Ch 41/43).

A customer-facing prompt box *will* be attacked — for sport, for free compute, and for data.
The PLAN names two distinct jobs that both live at the front door:

1. **Content guardrails** — block prompt injection / unsafe content, redact PII. We do **not**
   reimplement these: the ``llm-gateway`` blueprint already runs them on every call through its
   :class:`~llm_gateway.Guard` (Ch 41), and the copilot routes *through* the gateway, so they
   are on by construction. This module composes that guard for the explicit pre-checks the demo
   shows and adds the public-surface concerns the gateway can't know about.

2. **Abuse resistance** — a public surface needs a **per-user rate limit** so one attacker (or a
   runaway client) can't burn your margin or DoS the model. Unit economics are a product
   feature here (PLAN.md → "unit economics must fit the subscription margin"), so the limiter is
   keyed by the authenticated *(tenant, user)* — never by IP, which is trivially rotated.

The limiter is an in-memory fixed-window counter: enough to *demonstrate and test* the policy
offline with no deps. Swap it for Redis/token-bucket in production; the seam (``check`` raises
:class:`RateLimitError`, ``allow`` returns a bool) is identical.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from . import _compose  # noqa: F401  (side effect: pattern blueprints on sys.path)

from llm_gateway import Guard, GuardResult  # type: ignore  # noqa: E402


class RateLimitError(RuntimeError):
    """Raised when an authenticated user exceeds their per-window request budget."""

    def __init__(self, label: str, limit: int) -> None:
        super().__init__(f"rate limit exceeded for {label!r}: > {limit} requests/window")
        self.label = label
        self.limit = limit


@dataclass
class RateLimiter:
    """A per-user fixed-window request limiter — the cheapest useful abuse bound.

    ``limit`` requests are allowed per logical window; the (count, window) is keyed by the
    *(tenant, user)* label so the budget follows identity, not network address. This protects
    both the model bill (margin) and availability (one user can't starve others).

    For the demo and tests the window is advanced manually (``tick``) so behavior is
    deterministic and no wall-clock sleeping is needed. A production limiter keys the window on
    ``time.time() // window_seconds`` and/or uses a token bucket for smoother shaping.
    """

    limit: int = 5
    _window: int = 0
    _counts: dict[tuple[int, str], int] = field(default_factory=lambda: defaultdict(int))

    def tick(self) -> None:
        """Advance to a fresh window, resetting every user's budget."""
        self._window += 1

    def allow(self, label: str) -> bool:
        """Record one request for ``label``; return ``True`` if it is within budget."""
        key = (self._window, label)
        self._counts[key] += 1
        return self._counts[key] <= self.limit

    def remaining(self, label: str) -> int:
        """Requests still allowed for ``label`` in the current window (never negative)."""
        used = self._counts[(self._window, label)]
        return max(0, self.limit - used)

    def check(self, label: str) -> None:
        """Raise :class:`RateLimitError` if ``label`` is over budget (else record + pass)."""
        if not self.allow(label):
            raise RateLimitError(label, self.limit)


@dataclass(frozen=True)
class FrontDoorVerdict:
    """The combined front-door decision for one incoming message."""

    allowed: bool
    reason: str
    guard: GuardResult
    rate_limited: bool = False

    @property
    def blocked(self) -> bool:
        return not self.allowed


class FrontDoor:
    """The public-surface gatekeeper: rate limit, then content guard, before any model spend.

    Order matters and is deliberate: **rate-limit first** (cheapest, stops a flood before it
    costs anything), then run the gateway's content :class:`~llm_gateway.Guard` to catch
    injection / unsafe content and redact PII. Only a message that survives both reaches the
    copilot's agent loop and the (metered) model call.

    This *composes* the gateway guard — it does not fork it — so a detector improved in
    ``llm-gateway`` improves every solution that routes through it, this one included.
    """

    def __init__(
        self,
        *,
        guard: Guard | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.guard = guard if guard is not None else Guard()
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()

    def check(self, label: str, message: str) -> FrontDoorVerdict:
        """Vet one message from an authenticated user. Never raises — returns a verdict.

        ``label`` is the *(tenant, user)* attribution string (``Session.label``). A blocked
        verdict carries the reason so the surface can show a friendly refusal and the
        observability stack can record an abuse signal.
        """
        # 1 — abuse bound (per-user, cheapest gate, protects margin + availability).
        if not self.rate_limiter.allow(label):
            empty = GuardResult(text=message, findings=[])
            return FrontDoorVerdict(
                allowed=False,
                reason=f"rate_limited: > {self.rate_limiter.limit} requests/window",
                guard=empty,
                rate_limited=True,
            )

        # 2 — content guard (injection / unsafe block; PII redact) via the gateway's Guard.
        guard_result = self.guard.check_input(message)
        if guard_result.blocked:
            categories = ", ".join(
                f.category for f in guard_result.findings if f.action.value == "block"
            )
            return FrontDoorVerdict(
                allowed=False,
                reason=f"guardrail_block: {categories}",
                guard=guard_result,
            )

        # Allowed — note: ``guard_result.text`` is the PII-redacted prompt to forward downstream.
        reason = "redacted_pii" if guard_result.redacted else "ok"
        return FrontDoorVerdict(allowed=True, reason=reason, guard=guard_result)
