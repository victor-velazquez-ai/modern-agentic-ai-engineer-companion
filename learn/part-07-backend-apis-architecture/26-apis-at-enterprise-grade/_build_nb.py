"""Builder for the Ch 26 companion notebooks. Run once, then delete.

Produces valid nbformat-4 .ipynb files with cleared outputs and execution_count=null.
Cell source text is authored as plain strings here and split into the line-list shape
the repo uses. No notebook is executed; outputs stay empty.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text}


def finalize(cells, name):
    for c in cells:
        s = c["source"]
        if isinstance(s, str):
            lines = s.splitlines(keepends=True)
            c["source"] = lines if lines else [""]
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    out = os.path.join(DIR, name)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    return out


# ---------------------------------------------------------------------------
# 26-01 — Authn vs authz: JWTs, RBAC, and the broken-object hole
# ---------------------------------------------------------------------------
def build_2601():
    BR = "\U0001F4D3"   # book/companion
    BRAIN = "\U0001F9E0"
    CRYSTAL = "\U0001F52E"
    WRENCH = "\U0001F527"
    TARGET = "\U0001F3AF"
    PKG = "\U0001F9F1"
    BUILD = "\U0001F3D7️"
    c = []

    c.append(md(
        "# Authn vs authz: JWTs, RBAC, and the broken-object hole\n"
        "\n"
        f"> {BR} *Companion to* **Modern Agentic AI Engineer** *· Ch 26 §26.2 · type: walkthrough*\n"
        "\n"
        "**One-line promise:** secure a FastAPI service with bearer JWTs (authn as a `Depends`), "
        "gate an admin route with a role claim (authz/RBAC), then reproduce — and close — the "
        "OWASP broken-object-level-authorization hole, all offline with no live IdP."
    ))

    c.append(md(
        f"## {BRAIN} Why this matters\n"
        "\n"
        "Two questions get constantly confused, and you must answer both on *every* request. "
        "**Authentication** (authn) asks *who are you?* — a bearer token you verify. "
        "**Authorization** (authz) asks *what are you allowed to do?* — a role check, and, the part "
        "people forget, an *ownership* check on the specific resource.\n"
        "\n"
        "The single most dangerous API bug is the one where authn passes but authz is missing: the "
        "endpoint knows you're a logged-in user, then hands you someone else's record because you "
        "changed an id in the URL. That's **broken object-level authorization (BOLA)** — perennially "
        "#1 on the OWASP API Top 10. We build the auth, reproduce the breach in three lines, then "
        "close it by centralizing the check so it's the default, not per-endpoint memory."
    ))

    c.append(md(
        "## Objectives & prereqs\n"
        "\n"
        "**By the end you can:**\n"
        "- Mint and verify an HS256 JWT (here with the stdlib so the notebook stays dependency-free) "
        "and expose authn as a `current_user` dependency that raises `401` on a bad or expired token.\n"
        "- Trace where that token comes from in an OAuth2 / OIDC authorization-code flow — as a "
        "diagram plus a *mocked* token exchange (no live IdP).\n"
        "- Enforce **RBAC** so an admin-only route returns `403` for non-admins.\n"
        "- Spot and fix the **BOLA** hole by centralizing the ownership/tenant check.\n"
        "\n"
        "**Prereqs:** Ch 25 (FastAPI, `Depends`) and Ch 24 (`401` vs `403` semantics). No API key, no "
        "IdP, no network — everything is signed and verified locally."
    ))

    c.append(code(
        "# --- Setup: imports, env, and the MOCK switch ---------------------------------\n"
        "# stdlib only (+ python-dotenv & fastapi from requirements.txt). No network is used.\n"
        "import os\n"
        "import json\n"
        "import time\n"
        "import base64\n"
        "import hmac\n"
        "import hashlib\n"
        "import pathlib\n"
        "\n"
        "try:\n"
        "    from dotenv import load_dotenv\n"
        "    load_dotenv()\n"
        "except ImportError:\n"
        "    pass\n"
        "\n"
        "# Offline by design: JWTs are signed/verified locally and the OAuth2 exchange is mocked.\n"
        "# MOCK=0 would only matter if you wired a real IdP; the lesson runs fully in MOCK=1.\n"
        'MOCK = os.getenv("COMPANION_MOCK", "1") == "1"\n'
        "\n"
        "# The signing secret comes from the environment ONLY -- never hardcode it. We fall back to\n"
        "# a clearly-fake dev secret so the notebook runs with no setup; a real service would fail\n"
        "# fast if this were unset.\n"
        'JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-not-a-real-secret")\n'
        "\n"
        'DATA = pathlib.Path("data")\n'
        'fixture = json.loads((DATA / "users.json").read_text())\n'
        'USERS = {u["id"]: u for u in fixture["users"]}\n'
        'DOCS = {d["id"]: d for d in fixture["documents"]}\n'
        "\n"
        "have_env = \"JWT_SECRET\" in os.environ\n"
        'print(f"MOCK mode: {MOCK}  | secret from env: {have_env} (dev fallback otherwise)")\n'
        'print("users :", ", ".join(USERS))\n'
        'print("docs  :", ", ".join(d["id"] + "(owner=" + d["owner"] + ")" for d in DOCS.values()))'
    ))

    c.append(md(
        "## 1 · A JWT, demystified (§26.2)\n"
        "\n"
        "A JWT is three base64url segments joined by dots: `header.payload.signature`. The header "
        "and payload are *not encrypted* — just encoded — so never put secrets in a JWT. The "
        "signature is an HMAC over `header.payload` using your secret; that's what makes the token "
        "unforgeable. We implement sign/verify in ~15 lines of stdlib so you can see exactly what "
        "the `jwt` (PyJWT) library does for you."
    ))

    c.append(code(
        "# A minimal HS256 JWT, by hand, so nothing is magic. In production you'd use PyJWT:\n"
        '#     import jwt; jwt.encode(claims, secret, algorithm="HS256")  # book §26.2\n'
        "# but the bytes are identical -- a signed, base64url-encoded header.payload.signature.\n"
        "\n"
        "def _b64url(raw: bytes) -> str:\n"
        '    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()\n'
        "\n"
        "def _b64url_decode(seg: str) -> bytes:\n"
        '    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))\n'
        "\n"
        "def jwt_encode(claims: dict, secret: str) -> str:\n"
        '    header = {"alg": "HS256", "typ": "JWT"}\n'
        '    h = _b64url(json.dumps(header, separators=(",", ":")).encode())\n'
        '    p = _b64url(json.dumps(claims, separators=(",", ":")).encode())\n'
        '    signing_input = f"{h}.{p}".encode()\n'
        "    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()\n"
        '    return f"{h}.{p}.{_b64url(sig)}"\n'
        "\n"
        "class JWTError(Exception):\n"
        "    pass\n"
        "\n"
        "def jwt_decode(token: str, secret: str) -> dict:\n"
        "    try:\n"
        '        h, p, s = token.split(".")\n'
        "    except ValueError:\n"
        '        raise JWTError("malformed token")\n'
        '    expected = _b64url(hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())\n'
        "    # constant-time compare defeats signature-timing attacks\n"
        "    if not hmac.compare_digest(expected, s):\n"
        '        raise JWTError("bad signature")\n'
        "    claims = json.loads(_b64url_decode(p))\n"
        '    if "exp" in claims and claims["exp"] < time.time():\n'
        '        raise JWTError("expired token")\n'
        "    return claims\n"
        "\n"
        "def mint_token(user_id: str, ttl_seconds: int = 3600) -> str:\n"
        "    u = USERS[user_id]\n"
        "    now = int(time.time())\n"
        "    return jwt_encode({\n"
        '        "sub": user_id,            # subject = who\n'
        '        "tenant": u["tenant"],     # tenant for multi-tenant scoping (Ch 28)\n'
        '        "roles": u["roles"],       # role claims drive RBAC\n'
        '        "iat": now,\n'
        '        "exp": now + ttl_seconds,\n'
        "    }, JWT_SECRET)\n"
        "\n"
        'alice_token = mint_token("u_alice")\n'
        'print("alice\'s token (note the 3 dot-separated segments):")\n'
        "print(alice_token)\n"
        'print("\\ndecoded claims:", jwt_decode(alice_token, JWT_SECRET))'
    ))

    c.append(md(
        f"{CRYSTAL} **Predict.** We flip a single character in the token's payload and verify it "
        "again. Will `jwt_decode` (a) return the tampered claims, (b) raise `bad signature`, or "
        "(c) raise `expired token`? Decide before running."
    ))

    c.append(code(
        "# Tamper: flip characters in the middle (payload) segment.\n"
        'h, p, s = alice_token.split(".")\n'
        'tampered = f"{h}.{p[:-2]}XY.{s}"\n'
        "try:\n"
        "    jwt_decode(tampered, JWT_SECRET)\n"
        '    print("accepted (!!) -- this would be a forgery vulnerability")\n'
        "except JWTError as e:\n"
        '    print("rejected:", e)'
    ))

    c.append(md(
        "**What you just saw.** Any edit to header or payload changes the bytes the HMAC is "
        "computed over, so the signature no longer matches — `bad signature`. That's the whole "
        "security model: you can *read* a JWT without the secret, but you can't *alter* one."
    ))

    c.append(md(
        f"## 2 · Authn as a `Depends` — the book's `HTTPBearer` shape ({WRENCH} Build)\n"
        "\n"
        "In FastAPI you express authentication as a dependency: a `current_user` that pulls the "
        "bearer token off the `Authorization` header, decodes it, and raises `401` on failure. "
        "Every protected route just declares `user = Depends(current_user)`. This is the §26.2 shape:\n"
        "\n"
        "```python\n"
        "bearer = HTTPBearer()\n"
        "\n"
        "async def current_user(token = Depends(bearer)) -> User:\n"
        "    try:\n"
        '        claims = jwt.decode(token.credentials, settings.jwt_secret, algorithms=["HS256"])\n'
        "    except jwt.PyJWTError:\n"
        '        raise HTTPException(401, "invalid token")\n'
        '    return await load_user(claims["sub"])\n'
        "```\n"
        "\n"
        "We build the same thing against a real FastAPI app and exercise it with the in-process "
        "`TestClient` — no server, no network."
    ))

    c.append(code(
        "from fastapi import FastAPI, Depends, HTTPException, Header, Path\n"
        "from fastapi.testclient import TestClient\n"
        "\n"
        'app = FastAPI(title="Agent API", version="1.0.0")\n'
        "\n"
        'def current_user(authorization: str = Header(default="")) -> dict:\n'
        '    """Authn dependency: verify the bearer JWT or raise 401. Mirrors the book\'s\n'
        "    HTTPBearer + jwt.decode shape, using our stdlib jwt_decode.\"\"\"\n"
        '    if not authorization.startswith("Bearer "):\n'
        '        raise HTTPException(status_code=401, detail="missing bearer token")\n'
        '    token = authorization.removeprefix("Bearer ")\n'
        "    try:\n"
        "        claims = jwt_decode(token, JWT_SECRET)\n"
        "    except JWTError as e:\n"
        '        raise HTTPException(status_code=401, detail=f"invalid token: {e}")\n'
        '    user = USERS.get(claims["sub"])\n'
        "    if user is None:\n"
        '        raise HTTPException(status_code=401, detail="unknown subject")\n'
        "    # carry the verified claims (roles, tenant) alongside the user record\n"
        '    return {**user, "claims": claims}\n'
        "\n"
        '@app.get("/me")\n'
        "def me(user: dict = Depends(current_user)):   # authn as a dependency\n"
        '    return {"id": user["id"], "tenant": user["tenant"], "roles": user["claims"]["roles"]}\n'
        "\n"
        "client = TestClient(app)\n"
        "\n"
        'print("no token      ->", client.get("/me").status_code, "(expect 401)")\n'
        'print("garbage token ->", client.get("/me", headers={"Authorization": "Bearer not.a.jwt"}).status_code, "(expect 401)")\n'
        'ok = client.get("/me", headers={"Authorization": f"Bearer {alice_token}"})\n'
        'print("alice\'s token ->", ok.status_code, ok.json())'
    ))

    c.append(md(
        "**What you just saw.** One dependency centralizes verification. A missing or invalid token "
        "never reaches your handler — it stops at `401`. Note `401` means *\"I don't know who you "
        "are\"*; we'll meet its sibling `403` (*\"I know who you are; you may not\"*) next."
    ))

    c.append(md(
        "## 3 · Where does the token come from? OAuth2 / OIDC (mocked)\n"
        "\n"
        "For \"log in with Google/Okta/Entra,\" your app never sees the password. The "
        "**authorization-code flow** runs like this:\n"
        "\n"
        "```\n"
        " Browser            Your app (client)         Identity Provider (IdP)\n"
        "   |  click 'log in'      |                           |\n"
        "   |-------------------->  | redirect to IdP --------->|\n"
        "   |                      |        user authenticates |\n"
        "   | <----------------------- redirect back w/ CODE --|\n"
        "   |  ?code=abc           |                           |\n"
        "   |-------------------->  | exchange CODE + secret -->|\n"
        "   |                      | <-------- id_token (JWT) --|\n"
        "   |                      |  verify & start session   |\n"
        "```\n"
        "\n"
        "The IdP returns an **id_token** — itself a signed JWT — which is the token your "
        "`current_user` then verifies on each call. We mock the final exchange so you can see the "
        "shape without a live IdP."
    ))

    c.append(code(
        "def mock_oauth_exchange(auth_code: str) -> dict:\n"
        '    """Stand-in for POST /token at the IdP. A real client sends the code + client\n'
        "    secret over TLS and receives tokens; here we mint one locally for 'u_carol'.\"\"\"\n"
        "    if MOCK:\n"
        "        # The IdP would verify the code; we just map a known code to a known user.\n"
        '        assert auth_code == "mock-auth-code-xyz", "unexpected authorization code"\n'
        "        return {\n"
        '            "access_token": mint_token("u_carol"),\n'
        '            "token_type": "Bearer",\n'
        '            "expires_in": 3600,\n'
        "        }\n"
        '    raise RuntimeError("live IdP path not configured; wire an OIDC client to use MOCK=0")\n'
        "\n"
        'tokens = mock_oauth_exchange("mock-auth-code-xyz")\n'
        'shown = {k: (v[:24] + "..." if k == "access_token" else v) for k, v in tokens.items()}\n'
        'print("exchanged code for tokens:", shown)\n'
        "# That access_token is exactly what your API's current_user() verifies:\n"
        'who = client.get("/me", headers={"Authorization": f"Bearer {tokens[\'access_token\']}"})\n'
        'print("/me with the IdP-issued token ->", who.json())'
    ))

    c.append(md(
        f"## 4 · RBAC: a role claim gates an admin route ({WRENCH} Build)\n"
        "\n"
        "Authorization, first cut: **role-based access control**. The token already carries a "
        "`roles` claim; an admin-only route checks for `\"admin\"` and returns `403` otherwise. We "
        "express *this* as a dependency too, so the policy lives in one place."
    ))

    c.append(code(
        "def require_role(role: str):\n"
        '    """Authz dependency factory: 403 unless the verified user has `role`."""\n'
        "    def checker(user: dict = Depends(current_user)) -> dict:\n"
        '        if role not in user["claims"]["roles"]:\n'
        '            raise HTTPException(status_code=403, detail=f"requires role: {role}")\n'
        "        return user\n"
        "    return checker\n"
        "\n"
        '@app.get("/admin/metrics")\n'
        'def admin_metrics(user: dict = Depends(require_role("admin"))):\n'
        '    return {"ok": True, "viewer": user["id"]}\n'
        "\n"
        'carol_token = tokens["access_token"]  # carol is an admin (see fixture)\n'
        'h_alice = {"Authorization": f"Bearer {alice_token}"}\n'
        'h_carol = {"Authorization": f"Bearer {carol_token}"}\n'
        'print("alice (user)  ->", client.get("/admin/metrics", headers=h_alice).status_code, "(expect 403)")\n'
        'print("carol (admin) ->", client.get("/admin/metrics", headers=h_carol).status_code, "(expect 200)")'
    ))

    c.append(md(
        "**What you just saw.** Same authenticated users, different *authorization* outcomes. "
        "`401` vs `403` is not pedantry: `401` tells a client \"re-authenticate,\" `403` tells it "
        "\"don't bother, you lack permission.\" Returning the wrong one sends clients down the wrong "
        "recovery path."
    ))

    c.append(md(
        "## 5 · ⚠️ The dangerous one: broken object-level authorization (BOLA)\n"
        "\n"
        "Here is the bug that breaches real companies. We add a `GET /documents/{doc_id}` that "
        "authenticates the user — and then returns the document. It *feels* secure: you need a "
        "valid token. But it never checks whether *this* user owns *that* document.\n"
        "\n"
        f"{CRYSTAL} **Predict.** Alice is authenticated. `doc_2` belongs to **Bob**. What status and "
        "body does `GET /documents/doc_2` return with Alice's token? Decide before running."
    ))

    c.append(code(
        "# THE VULNERABLE VERSION -- authn present, object-level authz MISSING.\n"
        '@app.get("/documents/{doc_id}")\n'
        "def get_document_vulnerable(doc_id: str = Path(...), user: dict = Depends(current_user)):\n"
        "    doc = DOCS.get(doc_id)\n"
        "    if doc is None:\n"
        '        raise HTTPException(status_code=404, detail="not found")\n'
        "    return doc   # <-- no ownership check: returns ANY doc to ANY logged-in user\n"
        "\n"
        "# Alice walks Bob's id by editing the URL -- the classic IDOR/BOLA attack.\n"
        'resp = client.get("/documents/doc_2", headers=h_alice)\n'
        'print("alice reads Bob\'s doc_2 ->", resp.status_code)\n'
        "print(resp.json())"
    ))

    c.append(md(
        "**What you just saw.** `200 OK` — Alice just read Bob's document by changing two "
        "characters in the URL. Authentication was never the problem; the *missing object-level "
        "authorization* check was. With `tenant` in play, the same hole leaks data *across "
        "customers* — the kind of incident that ends up in the press."
    ))

    c.append(md(
        f"### The fix: centralize the ownership/tenant check ({WRENCH} Build)\n"
        "\n"
        "The cure is not \"remember to add an `if` to every endpoint\" — that's how the bug recurs. "
        "Make the authorized lookup the *only* way to fetch a resource: a dependency that loads the "
        "object **and** asserts the caller owns it (and shares its tenant). Now forgetting the check "
        "is impossible because there's no unchecked path."
    ))

    c.append(code(
        "def authorized_document(doc_id: str = Path(...), user: dict = Depends(current_user)) -> dict:\n"
        '    """Load-and-authorize in ONE place. 404 if absent; deny (also 404) if not owner or\n'
        "    wrong tenant. Returning 404 for someone else's resource avoids leaking its existence.\"\"\"\n"
        "    doc = DOCS.get(doc_id)\n"
        "    if doc is None:\n"
        '        raise HTTPException(status_code=404, detail="not found")\n'
        '    same_tenant = doc["tenant"] == user["tenant"]\n'
        '    is_owner = doc["owner"] == user["id"]\n'
        '    is_admin = "admin" in user["claims"]["roles"]\n'
        "    if not (same_tenant and (is_owner or is_admin)):\n"
        '        raise HTTPException(status_code=404, detail="not found")  # deny == 404, hide existence\n'
        "    return doc\n"
        "\n"
        '@app.get("/v2/documents/{doc_id}")\n'
        "def get_document_safe(doc: dict = Depends(authorized_document)):\n"
        "    return doc   # the handler is trivial; the policy lives in the dependency\n"
        "\n"
        'a = client.get("/v2/documents/doc_2", headers=h_alice)\n'
        'print("alice -> Bob\'s doc_2 :", a.status_code, "(expect 404 -- denied, existence hidden)")\n'
        'b = client.get("/v2/documents/doc_1", headers=h_alice)\n'
        'print("alice -> her doc_1   :", b.status_code, b.json().get("title"))\n'
        'cc = client.get("/v2/documents/doc_3", headers=h_carol)\n'
        'print("carol -> globex doc_3:", cc.status_code, cc.json().get("title"))'
    ))

    c.append(md(
        "**What you just saw.** Same attack, now `404` — and Alice still reads her own document, "
        "Carol still reads hers. By making `authorized_document` the single door to a document, the "
        "ownership and tenant checks are the *default*, not a thing each endpoint must remember. We "
        "return `404` rather than `403` for another tenant's id so we don't even confirm it exists."
    ))

    c.append(md(
        f"## {TARGET} Senior lens\n"
        "\n"
        "The big judgment call in auth is **JWT vs server-side sessions**, and it comes down to "
        "*revocation*. A JWT is **stateless** — fast, no lookup, scales horizontally — but that's "
        "exactly why it's hard to kill: a stolen token is valid until it expires, because nothing "
        "checks a server record. Sessions invert the trade: a central store means you can revoke "
        "instantly (logout-everywhere, ban a user mid-incident), at the cost of a lookup per request "
        "and shared state across instances.\n"
        "\n"
        "The senior move is to pick by your revocation needs and often combine: short-lived access "
        "JWTs (minutes) plus a refresh token you *can* revoke; or JWTs with a small cached denylist "
        "of `jti`s checked on sensitive routes. And whichever you choose, enforce authz in *one* "
        "place — the centralized ownership/tenant dependency you just built — because BOLA is a "
        "process failure (a forgotten check), not a clever exploit."
    ))

    c.append(md(
        "## Recap\n"
        "\n"
        "- **Authn (`who?`) ≠ authz (`what may you do?`)**; enforce both, every request. `401` = "
        "re-authenticate; `403` = you lack permission.\n"
        "- A JWT is a *signed, readable* token: you can decode it without the secret, but not forge "
        "it. Never put secrets in the payload.\n"
        "- Express authn as a `current_user` **dependency** and RBAC as a `require_role(...)` "
        "dependency — policy in one place, trivial handlers.\n"
        "- OAuth2/OIDC's authorization-code flow is where the JWT comes from in \"log in with…\"; your "
        "API just verifies the resulting id/access token.\n"
        "- **BOLA** is the #1 API risk: authn present, object-level authz missing. Centralize the "
        "ownership/tenant check so the unchecked path doesn't exist; deny with `404` to hide existence."
    ))

    c.append(md(
        "## Exercises\n"
        "\n"
        "Predict the result before running each.\n"
        "\n"
        "1. **Expiry.** Mint a token with `ttl_seconds=1`, wait two seconds, and call `/me`. What "
        "status, and which `JWTError` fires inside `current_user`? Then mint with `ttl_seconds=-10` "
        "and explain the difference (if any).\n"
        "2. **Wrong secret = forgery defense.** Re-decode `alice_token` with a *different* "
        "`JWT_SECRET`. Which exception? Tie this back to why the secret must come from the "
        "environment and never ship in code.\n"
        "3. **Tenant isolation.** Add a fourth user in `globex` and a document they own, then verify "
        "Alice (acme) gets `404` on it via `/v2/documents/...`. Why is `404` a better deny code than "
        "`403` here?\n"
        "4. **ABAC tweak.** Extend `authorized_document` so a `\"viewer\"` role may *read* any doc in "
        "its own tenant but never another tenant's. Predict the matrix of outcomes for "
        "alice/bob/carol before testing."
    ))

    c.append(code("# Exercise 1 -- your code here\n"))
    c.append(code("# Exercise 2 -- your code here\n"))
    c.append(code("# Exercise 3 -- your code here\n"))
    c.append(code("# Exercise 4 -- your code here\n"))

    c.append(md(
        "## Next\n"
        "\n"
        "- ➡️ **Next notebook:** [`26-02-rate-limiting-quotas-errors-pagination.ipynb`]"
        "(./26-02-rate-limiting-quotas-errors-pagination.ipynb) — make the API defend itself: "
        "per-tenant rate limits with `429` + `Retry-After`, a structured error envelope, and cursor "
        "pagination.\n"
        f"- {BR} **Book:** §26.2 (authentication & authorization) — the `HTTPBearer` / "
        "`jwt.decode` shape and the BOLA pitfall.\n"
        f"- {PKG} **Template:** the auth dependency becomes a production default in "
        "[`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/).\n"
        f"- {BUILD} **Capstone:** wraps `capstone/app/` with auth + per-tenant scoping (checkpoint "
        "`ch26-enterprise-api`)."
    ))

    return finalize(c, "26-01-authn-authz-oauth2-jwt-rbac.ipynb")


# ---------------------------------------------------------------------------
# 26-02 — Self-protection & API conventions
# ---------------------------------------------------------------------------
def build_2602():
    BR = "\U0001F4D3"
    BRAIN = "\U0001F9E0"
    CRYSTAL = "\U0001F52E"
    WRENCH = "\U0001F527"
    TARGET = "\U0001F3AF"
    PKG = "\U0001F9F1"
    BUILD = "\U0001F3D7️"
    c = []

    c.append(md(
        "# Rate limits, quotas, structured errors, and cursor pagination\n"
        "\n"
        f"> {BR} *Companion to* **Modern Agentic AI Engineer** *· Ch 26 §26.3–§26.4 · type: walkthrough*\n"
        "\n"
        "**One-line promise:** make the API defend itself — a per-tenant sliding-window limiter that "
        "returns `429` + `Retry-After`, daily quotas, a consistent machine-readable error envelope, "
        "and cursor pagination — all offline against a shared in-memory store standing in for Redis."
    ))

    c.append(md(
        f"## {BRAIN} Why this matters\n"
        "\n"
        "A public API must protect *itself*. Without limits, one buggy client (or one bad actor) can "
        "exhaust your capacity, and — because each request here triggers an expensive model call — "
        "your budget too. **Rate limiting** caps requests per short window; **quotas** cap usage over "
        "a billing period. Both live in *shared* state so they hold across every server instance, and "
        "both are keyed *per tenant* so one customer can't starve another.\n"
        "\n"
        "The other half of \"enterprise-grade\" is *predictability*: structured errors a client can "
        "branch on (not prose to string-match), and pagination so a list endpoint never dumps an "
        "unbounded result. Pick these conventions once and every consumer benefits forever."
    ))

    c.append(md(
        "## Objectives & prereqs\n"
        "\n"
        "**By the end you can:**\n"
        "- Implement a sliding-window limiter keyed by API key + user + **tenant**, backed by a shared "
        "store, returning `429 Too Many Requests` with a correct `Retry-After`.\n"
        "- Have a client *honor* `Retry-After` and back off — the contract both sides rely on.\n"
        "- Distinguish a short-window **rate limit** from a per-day **quota**, and enforce both.\n"
        "- Return a consistent **error envelope** via one exception handler.\n"
        "- Page a list endpoint with an opaque **cursor**, and explain why offset breaks on changing data.\n"
        "\n"
        "**Prereqs:** notebook **26-01** (auth, tenant claim). No API key, no Redis, no network — a "
        "shared in-memory store stands in for Redis and the clock is faked for determinism."
    ))

    c.append(code(
        "# --- Setup: imports, env, and the MOCK switch ---------------------------------\n"
        "# stdlib only (+ python-dotenv & fastapi from requirements.txt). No network, no Redis.\n"
        "import os\n"
        "import json\n"
        "import time\n"
        "import base64\n"
        "import random\n"
        "import pathlib\n"
        "from collections import deque, defaultdict\n"
        "\n"
        "try:\n"
        "    from dotenv import load_dotenv\n"
        "    load_dotenv()\n"
        "except ImportError:\n"
        "    pass\n"
        "\n"
        'MOCK = os.getenv("COMPANION_MOCK", "1") == "1"\n'
        "random.seed(26)  # deterministic synthetic data below\n"
        "\n"
        "# A shared store stands in for Redis. In production this is a real Redis (or fakeredis in\n"
        "# tests) so limits hold ACROSS instances; the interface (incr/expiring keys) is the same.\n"
        "# We also fake the clock so the sliding window is fully deterministic in CI.\n"
        "class FakeClock:\n"
        "    def __init__(self, t=1_000_000.0):\n"
        "        self.t = t\n"
        "    def now(self):\n"
        "        return self.t\n"
        "    def advance(self, seconds):\n"
        "        self.t += seconds\n"
        "        return self.t\n"
        "\n"
        "clock = FakeClock()\n"
        'print(f"MOCK mode: {MOCK}  | shared store = in-memory (Redis stand-in); clock faked")'
    ))

    c.append(md(
        "## 1 · A sliding-window rate limiter, per tenant (§26.3, " + WRENCH + " Build)\n"
        "\n"
        "Key choice: a **sliding window** counts the requests in the last `window` seconds, so it "
        "doesn't suffer the burst-at-the-boundary problem of fixed windows. We store request "
        "timestamps per key in the shared store; the key is `tenant:user:api_key` so limits are "
        "scoped *per tenant* (Ch 28). When the count hits the cap we return how long until the oldest "
        "request ages out — that number becomes `Retry-After`."
    ))

    c.append(code(
        "class SlidingWindowLimiter:\n"
        '    """Per-key sliding window over a shared store. Returns (allowed, retry_after).\n'
        "    Backed here by an in-memory dict of deques; in prod, a Redis sorted-set per key.\"\"\"\n"
        "    def __init__(self, limit: int, window_s: float, clock: FakeClock):\n"
        "        self.limit = limit\n"
        "        self.window_s = window_s\n"
        "        self.clock = clock\n"
        "        self.hits = defaultdict(deque)  # key -> deque[timestamp]\n"
        "\n"
        "    def check(self, key: str):\n"
        "        now = self.clock.now()\n"
        "        dq = self.hits[key]\n"
        "        # drop timestamps older than the window (they no longer count)\n"
        "        while dq and dq[0] <= now - self.window_s:\n"
        "            dq.popleft()\n"
        "        if len(dq) >= self.limit:\n"
        "            # retry_after = when the oldest in-window hit will expire\n"
        "            retry_after = self.window_s - (now - dq[0])\n"
        "            return False, max(1, int(retry_after + 0.999))  # ceil, at least 1s\n"
        "        dq.append(now)\n"
        "        return True, 0\n"
        "\n"
        "def rate_key(tenant: str, user: str, api_key: str) -> str:\n"
        '    return f"{tenant}:{user}:{api_key}"\n'
        "\n"
        "# 3 requests / 10s, just to make the limit easy to hit in the demo.\n"
        "limiter = SlidingWindowLimiter(limit=3, window_s=10.0, clock=clock)\n"
        'print("limiter ready: 3 requests / 10s, keyed by tenant:user:api_key")'
    ))

    c.append(md(
        f"{CRYSTAL} **Predict.** With a limit of **3 per 10s**, tenant `acme` sends **5** requests at "
        "the same instant (the clock doesn't advance). How many get `allowed=True`, and what "
        "`Retry-After` does the *first rejected* one report? Decide before running."
    ))

    c.append(code(
        'key = rate_key("acme", "u_alice", "ak_live_123")\n'
        "results = []\n"
        "for i in range(5):\n"
        "    allowed, retry_after = limiter.check(key)\n"
        '    results.append((i + 1, allowed, retry_after))\n'
        'for n, allowed, ra in results:\n'
        '    verdict = "ALLOW" if allowed else f"429 (Retry-After: {ra}s)"\n'
        '    print(f"  request {n}: {verdict}")'
    ))

    c.append(md(
        "**What you just saw.** The first 3 pass; the 4th and 5th are rejected with `Retry-After: "
        "10` (nothing has aged out yet, so the full window remains). A *different* tenant has its own "
        "key and its own fresh budget — one customer can't consume another's."
    ))

    c.append(md(
        "## 2 · The client side of the contract: honor `Retry-After` (" + WRENCH + " Build)\n"
        "\n"
        "A `429` is only useful if clients respect it. A well-behaved client reads `Retry-After`, "
        "waits, then retries — instead of hammering and making the overload worse. We simulate that "
        "loop against the limiter using the faked clock (no real sleeping), so you can watch the "
        "back-off succeed once the window slides."
    ))

    c.append(code(
        "def well_behaved_client(limiter, key, max_tries=4):\n"
        '    """Try; on 429, advance the (faked) clock by Retry-After and retry."""\n'
        "    for attempt in range(1, max_tries + 1):\n"
        "        allowed, retry_after = limiter.check(key)\n"
        "        if allowed:\n"
        '            return f"succeeded on attempt {attempt}"\n'
        '        print(f"  attempt {attempt}: 429, backing off {retry_after}s (honoring Retry-After)")\n'
        "        limiter.clock.advance(retry_after)  # real client would time.sleep(retry_after)\n"
        '    return "gave up after backoff budget"\n'
        "\n"
        "# The key from section 1 is already at its limit; a polite client backs off and gets in.\n"
        "print(well_behaved_client(limiter, key))"
    ))

    c.append(md(
        "**What you just saw.** After waiting the advertised `Retry-After`, the oldest hits aged out "
        "of the window and the request succeeded. This is the entire social contract of rate "
        "limiting: the server says *how long*, the client *waits that long*. A client that ignores "
        "`Retry-After` and retries immediately just collects more `429`s."
    ))

    c.append(md(
        "## 3 · Rate limit ≠ quota (§26.3)\n"
        "\n"
        "Two different controls, often confused:\n"
        "\n"
        "- **Rate limit** — smooths *bursts*: \"≤ N requests per few seconds.\" Resets continuously.\n"
        "- **Quota** — caps *total volume per plan*: \"≤ 10,000 requests per day on the Pro plan.\" "
        "Resets on a calendar boundary; exceeding it usually means *upgrade*, not *wait a moment*.\n"
        "\n"
        "Quotas are naturally **per tenant** (it's the customer's plan). Here's a simple per-tenant "
        "daily counter alongside the limiter."
    ))

    c.append(code(
        "class DailyQuota:\n"
        '    """Per-tenant daily request counter in the shared store. Resets each UTC day."""\n'
        "    def __init__(self, plan_limits: dict, clock: FakeClock):\n"
        "        self.plan_limits = plan_limits        # plan -> requests/day\n"
        "        self.clock = clock\n"
        "        self.used = defaultdict(int)          # (tenant, day) -> count\n"
        "\n"
        "    def _day(self):\n"
        "        return int(self.clock.now() // 86400)\n"
        "\n"
        "    def charge(self, tenant: str, plan: str):\n"
        "        cap = self.plan_limits[plan]\n"
        "        slot = (tenant, self._day())\n"
        "        if self.used[slot] >= cap:\n"
        '            return False, {"used": self.used[slot], "limit": cap}\n'
        "        self.used[slot] += 1\n"
        '        return True, {"used": self.used[slot], "limit": cap}\n'
        "\n"
        'quota = DailyQuota({"free": 2, "pro": 10_000}, clock)\n'
        "# Simulate a free-plan tenant making 3 calls against a daily cap of 2.\n"
        "for i in range(3):\n"
        '    ok, info = quota.charge("acme", plan="free")\n'
        '    state = "OK" if ok else "QUOTA EXCEEDED (upgrade plan)"\n'
        '    print(f"  call {i + 1}: {state}  used={info[\'used\']}/{info[\'limit\']}")'
    ))

    c.append(md(
        "**What you just saw.** The third call is refused — not because of a *burst*, but because the "
        "*daily* allotment is spent. The right client response differs too: back off for a rate "
        "limit, upgrade (or wait until tomorrow) for a quota. Same `429`/`402` family, different "
        "remedy — which is exactly why your error body must say *which* it is."
    ))

    c.append(md(
        "## 4 · One structured error envelope (§26.4, " + WRENCH + " Build)\n"
        "\n"
        "Clients should branch on a stable **code**, never on your prose. The book's envelope:\n"
        "\n"
        "```json\n"
        '{ "error": { "code": "rate_limited", "message": "Too many requests.", "retry_after": 30 } }\n'
        "```\n"
        "\n"
        "Wire it once as a FastAPI exception handler so *every* error — yours and the framework's — "
        "comes out in the same shape. Now we mount the limiter as real middleware-ish dependency on a "
        "route and watch the `429` carry both the header and the envelope."
    ))

    c.append(code(
        "from fastapi import FastAPI, Depends, HTTPException, Header, Query\n"
        "from fastapi.responses import JSONResponse\n"
        "from fastapi.testclient import TestClient\n"
        "\n"
        'app = FastAPI(title="Agent API", version="1.0.0")\n'
        "\n"
        "class APIError(HTTPException):\n"
        '    """Carries a stable machine code + optional retry_after into the envelope."""\n'
        "    def __init__(self, status_code: int, code: str, message: str, retry_after: int | None = None):\n"
        "        super().__init__(status_code=status_code, detail=message)\n"
        "        self.code = code\n"
        "        self.retry_after = retry_after\n"
        "\n"
        "@app.exception_handler(APIError)\n"
        "def api_error_handler(request, exc: APIError):\n"
        '    body = {"error": {"code": exc.code, "message": exc.detail}}\n'
        "    headers = {}\n"
        "    if exc.retry_after is not None:\n"
        '        body["error"]["retry_after"] = exc.retry_after\n'
        '        headers["Retry-After"] = str(exc.retry_after)\n'
        "    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)\n"
        "\n"
        "# Fresh limiter for the endpoint demo (2 req / 60s) on its own clock.\n"
        "ep_clock = FakeClock()\n"
        "ep_limiter = SlidingWindowLimiter(limit=2, window_s=60.0, clock=ep_clock)\n"
        "\n"
        "def enforce_rate_limit(\n"
        '    x_tenant: str = Header(default="acme"),\n'
        '    x_user: str = Header(default="u_alice"),\n'
        '    x_api_key: str = Header(default="ak_live_123"),\n'
        "):\n"
        "    allowed, retry_after = ep_limiter.check(rate_key(x_tenant, x_user, x_api_key))\n"
        "    if not allowed:\n"
        '        raise APIError(429, "rate_limited", "Too many requests.", retry_after=retry_after)\n'
        '    return {"tenant": x_tenant, "user": x_user}\n'
        "\n"
        '@app.get("/v1/ping")\n'
        "def ping(ctx: dict = Depends(enforce_rate_limit)):\n"
        '    return {"ok": True, **ctx}\n'
        "\n"
        "client = TestClient(app)\n"
        'for i in range(3):\n'
        '    r = client.get("/v1/ping")\n'
        '    print(f"  request {i + 1}: HTTP {r.status_code}  Retry-After={r.headers.get(\'Retry-After\')}  body={r.json()}")'
    ))

    c.append(md(
        "**What you just saw.** The third call returns `429`, a `Retry-After` header, **and** the "
        "envelope `{\"error\": {\"code\": \"rate_limited\", ...}}`. A client reads `error.code`, sees "
        "`rate_limited`, and runs its back-off path — no string-matching, no guesswork. Every error "
        "in the service now shares this shape."
    ))

    c.append(md(
        "## 5 · Cursor pagination — never return an unbounded list (§26.4, " + WRENCH + " Build)\n"
        "\n"
        "⚠️ **Pitfall: the unbounded list.** A `GET /messages` that returns *everything* is a "
        "latency bomb and a memory bomb waiting for the dataset to grow. Always paginate. We use a "
        "**cursor** (an opaque token encoding \"start after id X\") rather than `?offset=`, because "
        "offset *skips by position* — when rows are inserted or deleted between pages, offset "
        "silently repeats or drops items. A cursor pins to a stable key, so it's correct on a "
        "changing dataset."
    ))

    c.append(code(
        "# Generate 200 synthetic messages (newest first) -- committed-size data made in-cell.\n"
        "MESSAGES = [\n"
        '    {"id": 1000 - i, "tenant": "acme", "text": f"message #{1000 - i}"}\n'
        "    for i in range(200)\n"
        "]  # ids 1000..801, descending\n"
        "\n"
        "def encode_cursor(last_id: int) -> str:\n"
        '    return base64.urlsafe_b64encode(json.dumps({"after": last_id}).encode()).decode()\n'
        "\n"
        "def decode_cursor(cursor: str) -> int:\n"
        '    return json.loads(base64.urlsafe_b64decode(cursor.encode()))["after"]\n'
        "\n"
        "@app.get(\"/v1/messages\")\n"
        "def list_messages(limit: int = Query(default=50, le=100), cursor: str | None = None):\n"
        '    """Cursor pagination: page by `id < after`, newest first. limit is CAPPED at 100."""\n'
        "    after = decode_cursor(cursor) if cursor else None\n"
        "    rows = MESSAGES if after is None else [m for m in MESSAGES if m[\"id\"] < after]\n"
        "    page = rows[:limit]\n"
        "    next_cursor = encode_cursor(page[-1][\"id\"]) if len(rows) > limit and page else None\n"
        '    return {"data": page, "next_cursor": next_cursor}\n'
        "\n"
        "# Walk the first two pages of 50.\n"
        'p1 = client.get("/v1/messages?limit=50").json()\n'
        'print("page 1:", len(p1["data"]), "rows, ids", p1["data"][0]["id"], "->", p1["data"][-1]["id"], "| next?", bool(p1["next_cursor"]))\n'
        'p2 = client.get(f"/v1/messages?limit=50&cursor={p1[\'next_cursor\']}").json()\n'
        'print("page 2:", len(p2["data"]), "rows, ids", p2["data"][0]["id"], "->", p2["data"][-1]["id"], "| next?", bool(p2[\'next_cursor\']))\n'
        "# The cap holds even if a client asks for more:\n"
        'capped = client.get("/v1/messages?limit=999")\n'
        'print("limit=999 ->", "HTTP", capped.status_code, "(422: limit must be <= 100, never unbounded)")'
    ))

    c.append(md(
        "**What you just saw.** Page 1 returns ids 1000→951, page 2 continues 950→901 via the "
        "cursor, and `limit=999` is *rejected* (`422`) because the schema caps it at 100. There is no "
        "way to ask this endpoint for an unbounded list — the pitfall is closed by construction."
    ))

    c.append(md(
        f"## {TARGET} Senior lens\n"
        "\n"
        "The expensive mistake here is *inconsistency*. Pick your conventions **once** and apply them "
        "everywhere: cursor (not offset) pagination, the single `{\"error\": {\"code\", ...}}` "
        "envelope, `snake_case` fields, ISO-8601 **UTC** timestamps, and `Retry-After` on every "
        "`429`. Every inconsistency is a tax each client pays forever — extra docs to read, extra "
        "branches to write, extra integration bugs. \n"
        "\n"
        "Two more senior notes. First, put the limiter's state in a *shared* store (Redis) from day "
        "one, even with a single instance — the day you scale out, an in-process counter silently "
        "lets through N× your limit. Second, decide your limiter's *failure mode*: if Redis is down, "
        "do you *fail open* (serve, risk overload) or *fail closed* (reject, risk an outage)? There's "
        "no universal answer, but there must be a *decision*, not an accident."
    ))

    c.append(md(
        "## Recap\n"
        "\n"
        "- A **sliding-window** limiter keyed by `tenant:user:api_key` returns `429` + `Retry-After`; "
        "the window slides so bursts at the boundary don't slip through.\n"
        "- The contract is two-sided: the server says *how long*, a well-behaved client **honors** "
        "`Retry-After`.\n"
        "- **Rate limit** (bursts, resets continuously) ≠ **quota** (per-plan volume, resets daily) — "
        "different remedies: back off vs upgrade.\n"
        "- One **error envelope** (`{\"error\": {\"code\", \"message\", \"retry_after\"}}`) via a "
        "single handler; clients branch on `code`, not prose.\n"
        "- **Cursor pagination** with a capped `limit` makes an unbounded list impossible and stays "
        "correct on changing data where offset doesn't.\n"
        "- Pick conventions once; **shared state** for limits; choose fail-open vs fail-closed "
        "deliberately."
    ))

    c.append(md(
        "## Exercises\n"
        "\n"
        "Predict the result before running each.\n"
        "\n"
        "1. **Window slide.** After hitting the limit in section 1, `clock.advance(5)` then check "
        "again — still `429`? Now advance another `6`s and check. Explain the `Retry-After` you'd "
        "expect at each step.\n"
        "2. **Token bucket vs sliding window.** Re-implement the limiter as a token bucket "
        "(capacity + refill rate). Which one allows a short burst above the average rate, and why "
        "might you *want* that for a bursty client?\n"
        "3. **Quota header.** Add `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers to the "
        "`/v1/ping` response. What should `Reset` be relative to — the window or the wall clock?\n"
        "4. **Offset breaks.** Build an offset-paginated version of `/v1/messages`, fetch page 1, "
        "*insert* a new newest message, then fetch page 2 by offset. Show the duplicate/skip. Why is "
        "the cursor immune?"
    ))

    c.append(code("# Exercise 1 -- your code here\n"))
    c.append(code("# Exercise 2 -- your code here\n"))
    c.append(code("# Exercise 3 -- your code here\n"))
    c.append(code("# Exercise 4 -- your code here\n"))

    c.append(md(
        "## Next\n"
        "\n"
        "- ⬅️ **Previous:** [`26-01-authn-authz-oauth2-jwt-rbac.ipynb`](./26-01-authn-authz-oauth2-jwt-rbac.ipynb).\n"
        "- ➡️ **Next notebook:** [`26-03-webhooks-and-openapi-contracts.ipynb`]"
        "(./26-03-webhooks-and-openapi-contracts.ipynb) — notify other systems reliably (signed, "
        "retried, idempotent webhooks) and gate API changes with a contract test against OpenAPI.\n"
        f"- {BR} **Book:** §26.3 (rate limiting, quotas, multi-tenancy) and §26.4 (pagination, "
        "filtering, errors).\n"
        f"- {PKG} **Template:** the limiter middleware and error envelope become defaults in "
        "[`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/); structured "
        "errors + request context feed [`blueprints/observability-stack/`](../../../blueprints/observability-stack/).\n"
        f"- {BUILD} **Capstone:** per-tenant limits wrap `capstone/app/` (checkpoint `ch26-enterprise-api`)."
    ))

    return finalize(c, "26-02-rate-limiting-quotas-errors-pagination.ipynb")


# ---------------------------------------------------------------------------
# 26-03 — Outbound events + contract testing
# ---------------------------------------------------------------------------
def build_2603():
    BR = "\U0001F4D3"
    BRAIN = "\U0001F9E0"
    CRYSTAL = "\U0001F52E"
    WRENCH = "\U0001F527"
    TARGET = "\U0001F3AF"
    PKG = "\U0001F9F1"
    BUILD = "\U0001F3D7️"
    c = []

    c.append(md(
        "# Webhooks (signed, retried, idempotent) + OpenAPI contract tests\n"
        "\n"
        f"> {BR} *Companion to* **Modern Agentic AI Engineer** *· Ch 26 §26.5–§26.6 · type: walkthrough*\n"
        "\n"
        "**One-line promise:** deliver outbound events the way you'd want to receive them — HMAC-"
        "signed, retried with backoff, idempotent on the consumer — then turn FastAPI's generated "
        "`openapi.json` into a contract test that fails the moment a field is renamed. All in-process."
    ))

    c.append(md(
        f"## {BRAIN} Why this matters\n"
        "\n"
        "Not every interaction is request→response. Sometimes *your* system must notify *theirs* — a "
        "long agent run finished, a document finished processing. That's a **webhook**: you `POST` an "
        "event to a URL the consumer registered. Three properties make webhooks trustworthy, and "
        "they're the same rigor you apply to your inbound API: **sign** them (so the receiver knows "
        "it's really you), **retry** them (the receiver may be briefly down — at-least-once "
        "delivery), and make the consumer **idempotent** (because at-least-once means you *will* send "
        "duplicates).\n"
        "\n"
        "The other source of truth in an enterprise API is the **OpenAPI spec** FastAPI generates for "
        "free. Pin it as a contract and a CI test catches breaking changes *before* they ship and "
        "break every client."
    ))

    c.append(md(
        "## Objectives & prereqs\n"
        "\n"
        "**By the end you can:**\n"
        "- Sign a webhook payload with an **HMAC** and have a receiver reject a *tampered* body.\n"
        "- Deliver with **retry + backoff** to a flaky receiver and reason about at-least-once.\n"
        "- Make the *consumer* **idempotent** with an idempotency key so a redelivered event is "
        "harmless (the Ch 24 pattern).\n"
        "- Dump FastAPI's `openapi.json` and write a **contract test** that fails when a field is "
        "renamed or removed.\n"
        "\n"
        "**Prereqs:** notebook **26-02**; Ch 24 (idempotency). Foreshadows Ch 29 (retries / "
        "at-least-once) and Ch 31 (n8n automations consuming these events). No network, no real "
        "outbound HTTP — receiver and delivery loop are in-process; the clock is faked."
    ))

    c.append(code(
        "# --- Setup: imports, env, and the MOCK switch ---------------------------------\n"
        "# stdlib only (+ python-dotenv & fastapi from requirements.txt). No outbound HTTP.\n"
        "import os\n"
        "import json\n"
        "import hmac\n"
        "import hashlib\n"
        "import random\n"
        "import pathlib\n"
        "\n"
        "try:\n"
        "    from dotenv import load_dotenv\n"
        "    load_dotenv()\n"
        "except ImportError:\n"
        "    pass\n"
        "\n"
        'MOCK = os.getenv("COMPANION_MOCK", "1") == "1"\n'
        "random.seed(26)  # deterministic 'flaky receiver' schedule below\n"
        "\n"
        "# The signing secret comes from the environment ONLY. Dev fallback so the notebook runs\n"
        "# with no setup; a real sender shares this secret with the receiver out of band.\n"
        'WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "whsec_dev-only-not-real")\n'
        "\n"
        'DATA = pathlib.Path("data")\n'
        'sample_event = json.loads((DATA / "webhook-event.json").read_text())\n'
        'print(f"MOCK mode: {MOCK}  | webhook secret from env: {\'WEBHOOK_SECRET\' in os.environ}")\n'
        'print("sample event:", sample_event["type"], "->", sample_event["data"]["run_id"])'
    ))

    c.append(md(
        "## 1 · Sign the payload so the receiver can trust it (§26.6, " + WRENCH + " Build)\n"
        "\n"
        "A webhook arrives at a public URL — anyone could `POST` to it. The fix is a shared-secret "
        "**HMAC** over the *exact bytes* of the body, sent in a header (Stripe/GitHub call it "
        "`X-Signature`). The receiver recomputes the HMAC over what it received and compares in "
        "constant time. Any change to the body changes the signature, so a tampered payload is "
        "rejected."
    ))

    c.append(code(
        "def sign_payload(body: bytes, secret: str) -> str:\n"
        '    """HMAC-SHA256 over the raw body bytes -> hex digest (the X-Signature header)."""\n'
        "    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()\n"
        "\n"
        "def verify_signature(body: bytes, signature: str, secret: str) -> bool:\n"
        "    expected = sign_payload(body, secret)\n"
        "    return hmac.compare_digest(expected, signature)  # constant-time\n"
        "\n"
        "# Serialize ONCE; sign and send the same bytes (re-serializing can reorder keys!).\n"
        'body = json.dumps(sample_event, separators=(",", ":"), sort_keys=True).encode()\n'
        "sig = sign_payload(body, WEBHOOK_SECRET)\n"
        'print("signature:", sig[:32], "...")\n'
        'print("verify untampered:", verify_signature(body, sig, WEBHOOK_SECRET))'
    ))

    c.append(md(
        f"{CRYSTAL} **Predict.** An attacker intercepts the event and flips the run's `status` from "
        "`succeeded` to `failed`, but **can't** recompute the HMAC (no secret). Does "
        "`verify_signature` on the tampered body return `True` or `False`? Decide before running."
    ))

    c.append(code(
        "tampered = dict(sample_event)\n"
        'tampered_data = dict(sample_event["data"])\n'
        'tampered_data["status"] = "failed"            # the attacker\'s edit\n'
        'tampered["data"] = tampered_data\n'
        'tampered_body = json.dumps(tampered, separators=(",", ":"), sort_keys=True).encode()\n'
        "\n"
        "# The attacker forwards the ORIGINAL signature (they can't make a valid new one).\n"
        "print(\"verify tampered body w/ original sig:\", verify_signature(tampered_body, sig, WEBHOOK_SECRET))"
    ))

    c.append(md(
        "**What you just saw.** `False` — the receiver recomputes the HMAC over the *bytes it got*, "
        "which no longer match the signature, so it rejects the event. Without the secret, an "
        "attacker can read or replay but cannot *forge*. (Replay is handled next, by idempotency.)"
    ))

    c.append(md(
        "## 2 · Deliver with retry + backoff to a flaky receiver (§26.6, " + WRENCH + " Build)\n"
        "\n"
        "The receiver might be briefly down (deploy, blip). **At-least-once** delivery means: retry "
        "with backoff until it succeeds or you exhaust the budget — then dead-letter it. We model a "
        "receiver that fails its first two attempts (e.g. `503`) and succeeds on the third, and a "
        "sender that backs off between tries (clock faked, no real sleeping)."
    ))

    c.append(code(
        "class FlakyReceiver:\n"
        '    """Verifies the signature, then fails `fail_times` before succeeding (503)."""\n'
        "    def __init__(self, fail_times: int, secret: str):\n"
        "        self.left = fail_times\n"
        "        self.secret = secret\n"
        "        self.deliveries = []   # bodies that were ACCEPTED (after a 200)\n"
        "    def receive(self, body: bytes, signature: str) -> int:\n"
        "        if not verify_signature(body, signature, self.secret):\n"
        "            return 401  # bad signature -> reject, do NOT process\n"
        "        if self.left > 0:\n"
        "            self.left -= 1\n"
        "            return 503  # transient: please retry\n"
        "        self.deliveries.append(body)\n"
        "        return 200\n"
        "\n"
        "def deliver_with_retry(receiver, body, signature, *, max_attempts=5, base=1.0):\n"
        '    """At-least-once delivery: retry transient failures with exponential backoff."""\n'
        "    delays = []\n"
        "    for attempt in range(1, max_attempts + 1):\n"
        "        status = receiver.receive(body, signature)\n"
        "        if status == 200:\n"
        '            return {"ok": True, "attempts": attempt, "delays": delays}\n'
        "        if status == 401:\n"
        '            return {"ok": False, "attempts": attempt, "reason": "bad signature (no retry)"}\n'
        "        if attempt < max_attempts:\n"
        "            backoff = base * (2 ** (attempt - 1))\n"
        "            delays.append(backoff)        # real sender would time.sleep(backoff)\n"
        '    return {"ok": False, "attempts": max_attempts, "reason": "exhausted (dead-letter it)"}\n'
        "\n"
        "receiver = FlakyReceiver(fail_times=2, secret=WEBHOOK_SECRET)\n"
        'print("delivering... (receiver fails twice, then 200)")'
    ))

    c.append(md(
        f"{CRYSTAL} **Predict.** The receiver fails the first **2** attempts, then returns `200`. How "
        "many *total* attempts before success, and what backoff delays were used between them "
        "(base 1s, doubling)? Decide before running."
    ))

    c.append(code(
        "result = deliver_with_retry(receiver, body, sig)\n"
        "print(result)\n"
        'print("accepted deliveries at receiver:", len(receiver.deliveries))'
    ))

    c.append(md(
        "**What you just saw.** Three attempts: fail (wait 1s), fail (wait 2s), succeed. The event "
        "was delivered exactly once *to the application* here — but at-least-once means that in the "
        "real world a `200` can be lost on the way back, and you'd retry an *already-processed* "
        "event. That's the next problem."
    ))

    c.append(md(
        "## 3 · ⚠️ Pitfall: a non-idempotent consumer (the Ch 24 fix, " + WRENCH + " Build)\n"
        "\n"
        "At-least-once delivery **guarantees** the consumer will eventually see duplicates — a "
        "retried event whose previous `200` was lost in transit. If the handler isn't idempotent, a "
        "duplicate \"run completed\" event might charge the customer twice or kick off the downstream "
        "automation twice. The fix is the Ch 24 idempotency key: dedupe on the event id so a "
        "redelivery is a harmless no-op."
    ))

    c.append(code(
        "# A non-idempotent handler: every delivery triggers the side effect.\n"
        "charges_naive = []\n"
        "def handle_naive(event):\n"
        '    charges_naive.append(event["data"]["run_id"])   # side effect: bill the run\n'
        "\n"
        "# Same event delivered THREE times (at-least-once duplicates).\n"
        "for _ in range(3):\n"
        "    handle_naive(sample_event)\n"
        'print("naive handler -> charges fired:", len(charges_naive), "(duplicated!)")\n'
        "\n"
        "# The idempotent handler: dedupe on the event id (its idempotency key).\n"
        "_seen = set()\n"
        "charges_idem = []\n"
        "def handle_idempotent(event):\n"
        '    key = event["id"]                 # stable per logical event, not per delivery\n'
        "    if key in _seen:\n"
        "        return  # already processed -> no-op (the whole point)\n"
        "    _seen.add(key)\n"
        '    charges_idem.append(event["data"]["run_id"])\n'
        "\n"
        "for _ in range(3):\n"
        "    handle_idempotent(sample_event)\n"
        'print("idempotent handler -> charges fired:", len(charges_idem), "(exactly once)")\n'
        'assert len(charges_idem) == 1, "idempotency must collapse redeliveries to one effect"'
    ))

    c.append(md(
        "**What you just saw.** Same three deliveries: the naive handler billed the run **3×**; the "
        "idempotent handler billed it **once** and ignored the replays. Sign + retry + idempotent "
        "is the trio — you can't safely have at-least-once delivery without an idempotent consumer."
    ))

    c.append(md(
        "## 4 · The OpenAPI spec as a contract test (§26.5, " + WRENCH + " Build)\n"
        "\n"
        "FastAPI generates an **OpenAPI** description of every endpoint for free. Treat it as the "
        "single source of truth: snapshot it, and a tiny **contract test** fails the build the moment "
        "a field or path is renamed/removed — catching a breaking change in CI before it ships and "
        "breaks every client (and it's the basis for generated SDKs). We build a small app, dump its "
        "`openapi.json`, and diff it against the committed baseline in `data/`."
    ))

    c.append(code(
        "from fastapi import FastAPI\n"
        "from pydantic import BaseModel\n"
        "\n"
        'app = FastAPI(title="Agent API", version="1.0.0")\n'
        "\n"
        "class RunRequest(BaseModel):\n"
        "    agent: str\n"
        "    prompt: str\n"
        "\n"
        "class Run(BaseModel):\n"
        "    run_id: str\n"
        "    status: str\n"
        "\n"
        '@app.post("/v1/runs", operation_id="create_run")\n'
        "def create_run(req: RunRequest) -> Run:\n"
        '    return Run(run_id="run_8a21", status="queued")\n'
        "\n"
        '@app.get("/v1/runs/{run_id}", operation_id="get_run")\n'
        "def get_run(run_id: str) -> Run:\n"
        '    return Run(run_id=run_id, status="succeeded")\n'
        "\n"
        "spec = app.openapi()\n"
        'print("generated paths:", sorted(spec["paths"].keys()))\n'
        'print("operationIds:", sorted(op["operationId"]\n'
        '                              for p in spec["paths"].values() for op in p.values()))'
    ))

    c.append(code(
        "# A focused contract test: paths + operationIds + path params must not silently change.\n"
        "def contract_surface(spec: dict) -> set:\n"
        '    """Reduce a spec to the surface clients depend on: (method, path, operationId)."""\n'
        "    surface = set()\n"
        '    for path, ops in spec["paths"].items():\n'
        "        for method, op in ops.items():\n"
        '            surface.add((method.upper(), path, op.get("operationId")))\n'
        "    return surface\n"
        "\n"
        'baseline = json.loads((DATA / "openapi-baseline.json").read_text())\n'
        "current = contract_surface(spec)\n"
        "expected = contract_surface(baseline)\n"
        "\n"
        "missing = expected - current      # something the baseline promised is gone -> BREAKING\n"
        "added = current - expected        # new surface -> usually safe, but flag it\n"
        'print("removed/renamed (BREAKING):", missing or "none")\n'
        'print("added (review):", added or "none")\n'
        'assert not missing, f"contract broke: {missing}"\n'
        'print("\\ncontract test PASSED -- current API still satisfies the committed contract")'
    ))

    c.append(md(
        f"{CRYSTAL} **Predict.** Suppose a teammate renames the field `run_id` to `id` (or changes "
        "`operation_id=\"get_run\"` to `\"fetch_run\"`). Will the contract test above pass or fail, "
        "and *which* set — `missing` or `added` — catches it? Think it through, then try it in "
        "Exercise 2."
    ))

    c.append(md(
        "**What you just saw.** The current API still satisfies the committed contract, so the test "
        "passes. Rename a path or `operationId` and `missing` becomes non-empty — the assertion "
        "fails, the CI job goes red, and the breaking change is stopped *before* it reaches a single "
        "consumer. This same spec is what SDK generators consume to emit typed clients."
    ))

    c.append(md(
        f"## {TARGET} Senior lens\n"
        "\n"
        "Treat **outbound** events with the same rigor as your **inbound** API. The asymmetry is "
        "seductive: the inbound API is obviously a contract — it has docs, tests, versioning — while "
        "webhooks feel like fire-and-forget. They aren't. An unsigned webhook is an open door; an "
        "un-retried one silently drops events the first time the receiver hiccups; a non-idempotent "
        "consumer double-charges on the inevitable duplicate. Each of those quietly erodes the trust "
        "that makes an integration valuable.\n"
        "\n"
        "So: sign them, retry with backoff and a dead-letter, make consumers idempotent, version the "
        "payload (`type` + a schema), and — yes — contract-test the *event* shape too, not just the "
        "REST surface. The difference between a platform partners build on and one they rip out is "
        "exactly this rigor applied to the events nobody sees until they break."
    ))

    c.append(md(
        "## Recap\n"
        "\n"
        "- A webhook is *your* system `POST`-ing an event to a URL the consumer registered — for "
        "work that finishes asynchronously (a long agent run).\n"
        "- **Sign** the raw body with an HMAC; the receiver recomputes and compares in constant time, "
        "rejecting any tampered payload.\n"
        "- **Retry with backoff** for at-least-once delivery; exhaustion means dead-letter, not "
        "silent drop.\n"
        "- At-least-once **guarantees** duplicates, so the **consumer must be idempotent** — dedupe "
        "on the event id (the Ch 24 key).\n"
        "- FastAPI's generated **OpenAPI** spec is a contract: snapshot it and a tiny test fails CI "
        "when a path/field is renamed or removed — and it powers SDK generation.\n"
        "- Outbound events deserve the same rigor as the inbound API: signed, retried, idempotent, "
        "versioned, contract-tested."
    ))

    c.append(md(
        "## Exercises\n"
        "\n"
        "Predict the result before running each.\n"
        "\n"
        "1. **Exhaust the budget.** Set `FlakyReceiver(fail_times=10)` with `max_attempts=5`. What "
        "does `deliver_with_retry` return, and what are the backoff delays? Where would a real system "
        "send the event next (hint: dead-letter queue)?\n"
        "2. **Break the contract.** Rename `operation_id=\"get_run\"` to `\"fetch_run\"`, regenerate "
        "the spec, and re-run the contract test. Which set (`missing`/`added`) trips, and what "
        "exception surfaces?\n"
        "3. **Replay window.** Add a `timestamp` to the signature input and have the receiver reject "
        "events older than 5 minutes. Why does signing the timestamp (not just the body) matter for "
        "replay protection?\n"
        "4. **Idempotency key choice.** Change `handle_idempotent` to key on "
        "`event[\"data\"][\"run_id\"]` instead of `event[\"id\"]`. Construct two *different* events "
        "for the same run and predict whether the second is wrongly dropped. Why must the key match "
        "the *logical event*, not the entity?"
    ))

    c.append(code("# Exercise 1 -- your code here\n"))
    c.append(code("# Exercise 2 -- your code here\n"))
    c.append(code("# Exercise 3 -- your code here\n"))
    c.append(code("# Exercise 4 -- your code here\n"))

    c.append(md(
        "## Next\n"
        "\n"
        "- ⬅️ **Previous:** [`26-02-rate-limiting-quotas-errors-pagination.ipynb`](./26-02-rate-limiting-quotas-errors-pagination.ipynb).\n"
        "- ➡️ **Part VIII** takes this enterprise-grade API to the cloud; **Ch 29** revisits retries / "
        "at-least-once in depth, and **Ch 31** consumes these webhooks in n8n automations.\n"
        f"- {BR} **Book:** §26.5 (OpenAPI, contract testing, SDKs) and §26.6 (webhooks, event-driven APIs).\n"
        f"- {PKG} **Template:** the webhook sender (sign + retry) and contract test become defaults in "
        "[`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/).\n"
        f"- {BUILD} **Capstone:** signed webhooks connect `capstone/app/` to `capstone/workers/` "
        "automations (checkpoint `ch26-enterprise-api`)."
    ))

    return finalize(c, "26-03-webhooks-and-openapi-contracts.ipynb")


if __name__ == "__main__":
    print(build_2601())
    print(build_2602())
    print(build_2603())
