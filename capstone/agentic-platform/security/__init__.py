"""The platform's structural-safety layer (Appendix C · ``security/`` · Ch 41).

"Prompts ask; structure enforces." This package is the enforcement: the cross-cutting security
posture consolidated into one reviewable place, so you can read the platform's safety story
without grepping five modules. It does not replace the enforcement *points* elsewhere — the
gateway guards in ``llm/gateway.py`` and the tool scopes in ``mcp/`` — it *defines the policy*
those points apply, and adds the pieces that have no other home.

Layout
------
``guards.py``          input/output guardrails: prompt-injection block, PII redaction,
                       unsafe-content block. The same detectors the ``llm/`` gateway runs.
``permissions.py``     tool-permission **tiers** (read / write / sensitive / admin): a tool's
                       declared risk tier decides whether it runs, needs approval, or is denied.
``sandbox.py``         the **sandbox policy** for code-execution tools: resource limits, a
                       network/filesystem deny-by-default, and an import allow-list.
``delegated_auth.py``  **delegated auth**: scoped, short-lived credentials a tool is handed for
                       one call, so no tool holds an ambient, long-lived secret.
``audit.py``           the tamper-evident **audit** trail: an append-only, hash-chained log of
                       every security-relevant decision (who/what/why/allowed).

Everything is MOCK-runnable and dependency-free: the detectors, the tier table, the sandbox
policy check, the credential broker, and the audit chain all run offline with no keys and no
spend. Secrets (signing keys, broker roots) are read from the environment only.
"""

from __future__ import annotations

from .audit import AuditEvent, AuditLog, Decision
from .delegated_auth import (
    CredentialBroker,
    DelegatedCredential,
    Grant,
    ScopeError,
)
from .guards import (
    Guard,
    GuardAction,
    GuardConfig,
    GuardFinding,
    GuardrailError,
    GuardResult,
    detect_injection,
    detect_unsafe,
    redact_pii,
)
from .permissions import (
    AccessDecision,
    Outcome,
    PermissionError_,
    PermissionTier,
    Principal,
    ToolPermission,
    ToolPermissionRegistry,
    default_registry,
    permission_registry,
)
from .sandbox import (
    SandboxPolicy,
    SandboxViolation,
    check_code,
    default_policy,
    enforce_code,
)

__all__ = [
    # guards
    "Guard",
    "GuardConfig",
    "GuardResult",
    "GuardFinding",
    "GuardAction",
    "GuardrailError",
    "redact_pii",
    "detect_injection",
    "detect_unsafe",
    # permission tiers
    "PermissionTier",
    "Outcome",
    "Principal",
    "ToolPermission",
    "AccessDecision",
    "ToolPermissionRegistry",
    "default_registry",
    "permission_registry",
    "PermissionError_",
    # sandbox
    "SandboxPolicy",
    "SandboxViolation",
    "check_code",
    "enforce_code",
    "default_policy",
    # delegated auth
    "CredentialBroker",
    "DelegatedCredential",
    "Grant",
    "ScopeError",
    # audit
    "AuditLog",
    "AuditEvent",
    "Decision",
]

__version__ = "0.1.0"
