"""Authentication stub (Ch 26).

A minimal bearer-token dependency so every route can be protected from day one.
Out of the box it compares the presented token against ``AUTH_SECRET`` from the
environment. That is a *placeholder*, not real auth.

# TODO: wire your IdP. Replace ``verify_token`` with real verification —
# validate a JWT against your issuer's JWKS, check audience/expiry/scopes, and
# return a richer principal. Keep the ``Principal`` return type so routes that
# depend on it do not change.

When ``AUTH_SECRET`` is unset (e.g. local MOCK runs) auth is *open* so the
template runs out of the box. Set ``AUTH_SECRET`` to turn enforcement on.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.settings import Settings, get_settings

# auto_error=False so we can return a clear 401 ourselves instead of FastAPI's.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller.

    ▢ TODO: extend with the fields your routes need (org id, scopes, email...).
    """

    subject: str
    is_authenticated: bool = True


def verify_token(token: str, settings: Settings) -> Principal:
    """Validate a bearer token and return the caller's principal.

    Stub implementation: constant-time-ish equality against ``AUTH_SECRET``.
    # TODO: replace with real JWT/IdP verification.
    """
    if settings.auth_secret and token == settings.auth_secret:
        return Principal(subject="local-dev")
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

    - If ``AUTH_SECRET`` is unset, auth is disabled and an anonymous principal is
      returned (convenient for local/MOCK runs).
    - Otherwise a valid ``Authorization: Bearer <token>`` header is required.
    """
    if not settings.auth_secret:
        # Auth disabled for local/dev convenience. Set AUTH_SECRET to enforce.
        return Principal(subject="anonymous", is_authenticated=False)

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials, settings)
