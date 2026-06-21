"""Delegated auth (Ch 41) — scoped, short-lived credentials for tools.

The wrong way to give an agent's tool access to a downstream system is to hand it a long-lived
API key with broad rights. The right way is **delegation**: the platform holds the real,
privileged secret; when a tool needs to act, a broker mints a **narrowly-scoped, short-lived**
credential for exactly that call — one scope, one resource, a few seconds of validity — and the
tool never sees the root secret. If the credential leaks, it is nearly worthless: it expires in
seconds and can do only the one thing it was scoped to.

Three principles this enforces in code (not documentation):

1. **Least privilege.** A grant declares the exact scopes it covers (``refunds:write``,
   ``tickets:read``). A credential can be used only for an operation whose required scope is in
   its grant. Anything else raises :class:`ScopeError`.
2. **Short TTL.** Every credential carries an expiry; :meth:`DelegatedCredential.is_valid`
   (and the broker on redemption) rejects an expired token. Default TTL is seconds, not hours.
3. **No ambient secret.** The root secret lives in the environment
   (``DELEGATION_SIGNING_KEY``) and is read by the broker only — never passed to a tool, never
   logged. The token a tool holds is a signed, opaque grant, not the key.

This is a teaching-grade broker: the "signature" is an HMAC over the grant so a token can't be
forged or widened without the root key, and verification is constant-time. In production the
same shape is fulfilled by STS-style temporary credentials, OAuth token exchange, or a secrets
manager issuing dynamic leases — the *interface* (mint a scoped, expiring credential per call)
is what carries over.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field


class ScopeError(RuntimeError):
    """Raised when a credential is used outside its scope, after expiry, or with a bad signature."""


SIGNING_KEY_ENV = "DELEGATION_SIGNING_KEY"
# Used only in MOCK / local dev when no real signing key is configured. A real deployment sets
# DELEGATION_SIGNING_KEY from a secrets manager; this default keeps offline runs working without
# ever shipping a usable production secret.
_DEV_FALLBACK_KEY = "dev-only-delegation-key-not-for-production"


def _signing_key() -> bytes:
    """The HMAC root key, from the environment only (dev fallback for offline/MOCK runs)."""

    return os.getenv(SIGNING_KEY_ENV, _DEV_FALLBACK_KEY).encode("utf-8")


@dataclass(frozen=True)
class Grant:
    """A request to act: which principal, which scopes, against which resource, for how long."""

    principal_id: str
    scopes: frozenset[str]
    resource: str = "*"
    ttl_seconds: float = 30.0

    @staticmethod
    def of(
        principal_id: str,
        *scopes: str,
        resource: str = "*",
        ttl_seconds: float = 30.0,
    ) -> "Grant":
        if not scopes:
            raise ValueError("a grant must declare at least one scope")
        return Grant(
            principal_id=principal_id,
            scopes=frozenset(scopes),
            resource=resource,
            ttl_seconds=float(ttl_seconds),
        )


@dataclass(frozen=True)
class DelegatedCredential:
    """A minted, signed, expiring credential a tool carries for one call.

    The ``token`` is opaque to the tool: it is a base64 payload plus an HMAC signature the
    broker verifies on redemption. The structured fields are here so a caller can introspect
    scope/expiry without trusting the token, but authority comes from the *signature*, which
    only the broker (holding the root key) can produce or check.
    """

    credential_id: str
    principal_id: str
    scopes: frozenset[str]
    resource: str
    expires_at: float
    token: str = field(repr=False)

    def is_valid(self, *, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.expires_at

    def covers(self, scope: str, resource: str | None = None) -> bool:
        """True if this credential authorizes ``scope`` on ``resource`` (and hasn't expired)."""

        if not self.is_valid():
            return False
        if scope not in self.scopes:
            return False
        if resource is not None and self.resource not in ("*", resource):
            return False
        return True


class CredentialBroker:
    """Mints and verifies scoped, short-lived credentials. Holds the only reference to the key.

    A tool asks the broker for a credential (``mint``) just before it needs to act, uses it for
    exactly one downstream call, and the credential expires moments later. The broker is the
    single trust boundary: it owns the root secret and is the only thing that can sign or verify
    a token.
    """

    def __init__(self, *, signing_key: bytes | None = None) -> None:
        # Default to the env-provided key; an explicit key is for tests only.
        self._key = signing_key if signing_key is not None else _signing_key()

    def mint(self, grant: Grant, *, now: float | None = None) -> DelegatedCredential:
        """Issue a signed credential for ``grant``. Short TTL; scoped to the grant's scopes."""

        issued = now if now is not None else time.time()
        expires = issued + grant.ttl_seconds
        payload = {
            "cid": uuid.uuid4().hex,
            "sub": grant.principal_id,
            "scopes": sorted(grant.scopes),
            "resource": grant.resource,
            "exp": expires,
        }
        token = self._encode(payload)
        return DelegatedCredential(
            credential_id=payload["cid"],
            principal_id=grant.principal_id,
            scopes=frozenset(grant.scopes),
            resource=grant.resource,
            expires_at=expires,
            token=token,
        )

    def verify(
        self,
        token: str,
        *,
        scope: str,
        resource: str | None = None,
        now: float | None = None,
    ) -> DelegatedCredential:
        """Verify ``token`` and authorize ``scope`` on ``resource``; return the credential.

        Raises :class:`ScopeError` on a bad/forged signature, an expired token, or a
        scope/resource the credential does not cover. This is the call a downstream adapter
        makes to *redeem* a credential — it trusts the signature, not the caller's word.
        """

        payload = self._decode(token)  # raises ScopeError on a bad signature
        expires = float(payload.get("exp", 0.0))
        moment = now if now is not None else time.time()
        if moment >= expires:
            raise ScopeError("credential has expired")

        scopes = frozenset(payload.get("scopes", ()))
        if scope not in scopes:
            raise ScopeError(f"scope {scope!r} not granted (have {sorted(scopes)})")

        res = str(payload.get("resource", "*"))
        if resource is not None and res not in ("*", resource):
            raise ScopeError(f"resource {resource!r} not covered (granted {res!r})")

        return DelegatedCredential(
            credential_id=str(payload["cid"]),
            principal_id=str(payload["sub"]),
            scopes=scopes,
            resource=res,
            expires_at=expires,
            token=token,
        )

    # --- token codec (HMAC-signed, tamper-evident) ---------------------------------------

    def _encode(self, payload: dict) -> str:
        body = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        sig = hmac.new(self._key, body, hashlib.sha256).digest()
        return body.decode("ascii") + "." + base64.urlsafe_b64encode(sig).decode("ascii")

    def _decode(self, token: str) -> dict:
        try:
            body_b64, sig_b64 = token.split(".", 1)
            body = body_b64.encode("ascii")
            sig = base64.urlsafe_b64decode(sig_b64.encode("ascii"))
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise ScopeError("malformed credential token") from exc

        expected = hmac.new(self._key, body, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):  # constant-time; forged/widened tokens fail
            raise ScopeError("bad credential signature (forged or tampered)")

        return json.loads(base64.urlsafe_b64decode(body))


__all__ = [
    "CredentialBroker",
    "DelegatedCredential",
    "Grant",
    "ScopeError",
    "SIGNING_KEY_ENV",
]
