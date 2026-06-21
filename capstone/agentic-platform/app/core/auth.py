"""Authentication and tenant scoping (Ch 26).

A bearer-token dependency so every route is protected from day one, plus the multi-tenant
``Principal`` the routes carry through to the domain. Out of the box ``verify_token`` compares
the presented token against ``AUTH_SECRET`` — a *placeholder*, not real auth.

When ``AUTH_SECRET`` is unset (local / MOCK runs) auth is **open**: an anonymous principal bound
to the ``"public"`` tenant is returned so the service runs out of the box. Set ``AUTH_SECRET``
to turn enforcement on.

# TODO: wire your IdP. Replace ``verify_token`` with real verification — validate a JWT against
# your issuer's JWKS, check audience/expiry/scopes, derive the tenant from a claim, and return a
# richer ``Principal``. Keep the return type so routes that depend on it do not change.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

# auto_error=False so we can return a clear 401 ourselves instead of FastAPI's.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller and the tenant whose data they may touch.

    ``tenant_id`` is the multi-tenancy seam: every query the domain runs is scoped to it, so one
    tenant can never read another's runs or documents. ``scopes`` gates privileged operations
    (e.g. ``"runs:write"``, ``"documents:admin"``).
    """

    subject: str
    tenant_id: str
    is_authenticated: bool = True
    scopes: frozenset[str] = field(default_factory=frozenset)

    def has_scope(self, scope: str) -> bool:
        """True when this principal carries ``scope`` (or the ``"*"`` wildcard)."""
        return "*" in self.scopes or scope in self.scopes


def verify_token(token: str, settings: Settings) -> Principal:
    """Validate a bearer token and return the caller's principal.

    Stub implementation: constant-time equality against ``AUTH_SECRET``. A real implementation
    decodes a JWT and derives ``tenant_id`` / ``scopes`` from its claims.
    """
    expected = settings.auth_secret or ""
    if expected and hmac.compare_digest(token, expected):
        # The stub grants a single local tenant with full scope.
        return Principal(
            subject="local-dev",
            tenant_id="local",
            scopes=frozenset({"*"}),
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Principal:
    """FastAPI dependency that resolves the current principal.

    - If ``AUTH_SECRET`` is unset, auth is disabled and an anonymous ``public``-tenant principal
      is returned (convenient for local / MOCK runs).
    - Otherwise a valid ``Authorization: Bearer <token>`` header is required.
    """
    if not settings.auth_enabled:
        return Principal(
            subject="anonymous",
            tenant_id="public",
            is_authenticated=False,
            scopes=frozenset({"*"}),
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials, settings)


def require_scope(scope: str):
    """Build a dependency that 403s unless the principal carries ``scope``.

    Usage in a route::

        @router.post("/admin", dependencies=[Depends(require_scope("documents:admin"))])
    """

    def _checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}.",
            )
        return principal

    return _checker
