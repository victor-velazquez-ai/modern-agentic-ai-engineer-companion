"""In-process token-bucket rate limiting (Ch 26).

A small, dependency-free limiter so the API can shed load before it reaches the model layer.
Each key (here: the principal's tenant) gets a bucket that refills at ``rate_per_minute`` and
holds at most ``burst`` tokens; a request costs one token.

This is intentionally **in-process** — fine for a single instance and for tests. In production
the same interface is backed by Redis (atomic ``INCR`` + TTL, or a Lua token bucket) so the
limit is shared across replicas; ``RedisRateLimiter`` is the drop-in (▢ TODO, Ch 26/30).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status

from app.core.auth import Principal, get_current_principal
from app.core.config import Settings, get_settings


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    """Thread-safe in-memory token-bucket limiter keyed by an arbitrary string."""

    def __init__(self, *, rate_per_minute: int, burst: int) -> None:
        self._refill_per_second = rate_per_minute / 60.0
        self._capacity = float(burst)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, cost: float = 1.0) -> bool:
        """Consume ``cost`` tokens for ``key``; return ``False`` if the bucket is empty."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self._capacity, updated_at=now)
                self._buckets[key] = bucket
            # Refill based on elapsed time, capped at capacity.
            elapsed = now - bucket.updated_at
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_second)
            bucket.updated_at = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False


def _build_limiter(rate_per_minute: int, burst: int) -> TokenBucketRateLimiter:
    return TokenBucketRateLimiter(rate_per_minute=rate_per_minute, burst=burst)


# One process-wide limiter, built lazily from settings on first use.
_LIMITER: TokenBucketRateLimiter | None = None


def get_rate_limiter(
    settings: Settings = Depends(get_settings),
) -> TokenBucketRateLimiter:
    """Provide the shared limiter, constructing it once from settings."""
    global _LIMITER
    if _LIMITER is None:
        _LIMITER = _build_limiter(settings.rate_limit_per_minute, settings.rate_limit_burst)
    return _LIMITER


def enforce_rate_limit(
    principal: Principal = Depends(get_current_principal),
    limiter: TokenBucketRateLimiter = Depends(get_rate_limiter),
) -> None:
    """Dependency that 429s when the caller's tenant has exhausted its bucket."""
    if not limiter.allow(principal.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Slow down and retry shortly.",
            headers={"Retry-After": "1"},
        )
