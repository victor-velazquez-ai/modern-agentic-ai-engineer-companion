"""Application core: configuration, auth, rate limiting, and DI wiring (Ch 26, 28).

``core/`` holds the cross-cutting machinery every route and service leans on but no business
rule should own: the twelve-factor :class:`~app.core.config.Settings`, the bearer-auth
:class:`~app.core.auth.Principal` and its tenant scoping, an in-process token-bucket rate
limiter, and the dependency-injection providers that hand routes their collaborators. None of
this is domain logic — it is the frame the domain runs inside.
"""

from __future__ import annotations

__all__: list[str] = []
