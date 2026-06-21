# `security/` — guardrails, permission tiers, sandbox, delegated auth, audit

> Capstone subsystem · Appendix C `security/` (extends the tree) · built in **Ch 41** ·
> enforcement points live in [`llm/gateway.py`](../llm/) (guards) and [`mcp/`](../mcp/) (scopes).

The platform's **structural-safety** layer. *Prompts ask; structure enforces* — this directory
is the enforcement, consolidated into one reviewable place so the safety posture is a single
thing you can read and test, not a habit scattered across the codebase. It defines the policy
that the gateway guards and MCP tool scopes apply, and adds the pieces (permission tiers,
sandbox, delegated auth, audit) that have no other home.

Everything is dependency-free and MOCK-runnable: the detectors, the tier table, the sandbox
check, the credential broker, and the audit chain all run offline with no keys and no spend.
Secrets (the delegation signing key) are read from the environment only.

## Layout

```
security/
├── guards.py          input/output guardrails: injection block, PII redaction, unsafe block
├── permissions.py     tool-permission tiers (read/write/sensitive/admin) → allow/approve/deny
├── sandbox.py         sandbox policy for code-exec tools: limits, deny-by-default, AST check
├── delegated_auth.py  scoped, short-lived credentials minted per tool call (HMAC-signed)
└── audit.py           append-only, hash-chained, tamper-evident decision log
```

## The five controls

### Guardrails (`guards.py`)
One seam every model call passes through. **Input** guards block prompt-injection
("ignore previous instructions") and redact PII before the prompt leaves your perimeter;
**output** guards redact PII the model echoed and flag unsafe content. Fails **closed** on a
block (raises `GuardrailError`), **safe** on redaction. The `llm/gateway.py` runs this exact
`Guard` on every call; `security/` owns the policy.

```python
from security import Guard
text = Guard().enforce_input(user_prompt)   # redacted text, or raises on a blocked input
```

### Permission tiers (`permissions.py`)
Every tool is classified into a **risk tier** — `READ` / `WRITE` / `SENSITIVE` / `ADMIN`. The
tier (plus *who* is acting) decides the outcome: **allow**, **require human approval**, or
**deny**. Deny-by-default: an unregistered tool never runs. `SENSITIVE`+ default to needing
approval — the flag `agents/approvals.py` reads to pause a run.

```python
from security import permission_registry, Principal
decision = permission_registry().authorize("issue_refund", Principal.operator("op7"))
# decision.outcome -> Outcome.REQUIRE_APPROVAL
```

### Sandbox policy (`sandbox.py`)
Code execution is the most dangerous capability, so its `run_code` tool runs under a declared
`SandboxPolicy`: network off, filesystem-write off, an **import allow-list**, and CPU/memory/
output budgets. `check_code` is a pre-flight **AST check** that rejects disallowed imports,
`eval`/`exec`/`__import__`, and out-of-sandbox calls (`os.system`, `subprocess`, write-mode
`open`) *before* code reaches an executor. This is **defense in depth** — necessary, never
sufficient; the real isolation boundary (microVM / seccomp container / rlimited subprocess)
enforces the resource limits.

### Delegated auth (`delegated_auth.py`)
No tool holds a long-lived, broad secret. A `CredentialBroker` (the only holder of the root
key, from `DELEGATION_SIGNING_KEY`) mints a **narrowly-scoped, short-lived** credential per
call. A leaked token is nearly worthless — it expires in seconds and can do only its one
scope. The token is HMAC-signed, so it can't be forged or widened without the root key;
`verify` is constant-time and refuses out-of-scope, expired, or tampered tokens.

### Audit trail (`audit.py`)
Every security-relevant decision (tool allowed/denied, input blocked, credential minted,
approval) is appended to a **hash-chained** log: each event hashes `(prev_hash + content)`, so
any insertion, deletion, or edit breaks the chain and `verify()` catches it. Append-only,
JSONL-serializable, and tamper-evident — the accountable record of "what did the agent do, and
what stopped it?".

## How they compose (the request path)

```
user prompt ──▶ guards.check_input ──▶ agent loop
                                         │  picks a tool
                                         ▼
                           permissions.authorize(tool, principal)
                             ├─ allow ──────────────▶ run it
                             ├─ require_approval ───▶ agents/approvals.py holds the run
                             └─ deny ───────────────▶ refuse
                                         │ (on allow, for a privileged downstream call)
                                         ▼
                           delegated_auth.mint(scoped, short-TTL)  ──▶ tool acts, token expires
                                         │ (run_code tools only)
                                         ▼
                           sandbox.enforce_code  ──▶ isolated executor
                                         │
                                         ▼
            every decision above ──▶ audit.AuditLog.record (hash-chained)
            model output ──▶ guards.check_output ──▶ user
```

## Maps to the book & repo

- **Ch 41** — injection defenses, guardrails, permission tiers, sandboxing, delegated auth.
- **Enforcement points:** the same `Guard` runs in [`llm/gateway.py`](../llm/); tool **scopes**
  are declared in [`mcp/`](../mcp/); the approval flag is consumed by
  [`agents/approvals.py`](../agents/). This directory is the one reviewable home for the policy.
- **Feeds:** every decision is recorded to the audit log and is observable via
  [`observability/`](../observability/); injection red-teaming is run as an eval in
  [`evals/`](../evals/).
