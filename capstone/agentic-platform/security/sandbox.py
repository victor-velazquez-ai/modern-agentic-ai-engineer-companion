"""Sandbox policy for code-execution tools (Ch 41).

When an agent can *run code* (a ``run_code`` tool, a data-analysis step), that tool is the
single most dangerous capability in the platform: arbitrary code is arbitrary power. The
defense is a **policy** declared in one place — what the code may import, whether it may touch
the network or the filesystem, and the wall-clock / memory / output budgets it runs under — and
a **pre-flight static check** that rejects obviously-unsafe code *before* it is ever handed to
an executor.

This module is the *policy and the gate*, deliberately decoupled from the *executor*. In
production the executor is a real isolation boundary — a gVisor/Firecracker microVM, a
container with seccomp and no network, or a subprocess with ``resource`` rlimits and dropped
privileges. This file defines the contract that boundary must enforce and gives you a
dependency-free, deterministic check that runs in MOCK/CI with no sandbox installed. It is
**defense in depth**, not a substitute for real isolation: a static check is necessary, never
sufficient.

Deny-by-default throughout: network off, filesystem off, an explicit import allow-list, and a
blocklist of dangerous builtins/calls (``eval``, ``exec``, ``__import__``, ``os.system``,
``subprocess``, ``open`` for writing). Anything the policy does not explicitly allow is denied.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


class SandboxViolation(RuntimeError):
    """Raised when code (or a request) violates the sandbox policy (fail-closed)."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("sandbox policy violation: " + "; ".join(reasons))


# Modules safe to import inside the sandbox by default. Intentionally tiny — extend per use
# case, never broaden to "everything". No `os`, `sys`, `subprocess`, `socket`, `pathlib`.
_DEFAULT_ALLOWED_IMPORTS: frozenset[str] = frozenset(
    {"math", "statistics", "json", "re", "datetime", "decimal", "itertools", "collections"}
)

# Names that are unsafe to call/use regardless of imports — the usual code-exec escapes.
_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "__import__", "globals", "locals", "vars", "getattr", "setattr"}
)

# Dotted calls that punch out of the sandbox even from an allowed import.
_FORBIDDEN_ATTR_CALLS: frozenset[str] = frozenset(
    {"os.system", "os.popen", "subprocess.run", "subprocess.Popen", "socket.socket"}
)


@dataclass(frozen=True)
class SandboxPolicy:
    """The declared limits a code-execution tool runs under.

    The resource fields are the contract the *executor* must enforce (rlimits / cgroups / a
    microVM); :func:`check_code` enforces the static fields (imports, forbidden calls) before
    code reaches that executor. Both layers matter — defense in depth.
    """

    allow_network: bool = False
    allow_filesystem_write: bool = False
    allowed_imports: frozenset[str] = field(default=_DEFAULT_ALLOWED_IMPORTS)
    cpu_seconds: float = 5.0
    memory_mb: int = 256
    max_output_bytes: int = 64_000
    max_code_chars: int = 20_000

    def with_imports(self, *modules: str) -> "SandboxPolicy":
        """Return a copy that also allows ``modules`` (the only safe way to widen the list)."""

        return SandboxPolicy(
            allow_network=self.allow_network,
            allow_filesystem_write=self.allow_filesystem_write,
            allowed_imports=self.allowed_imports | frozenset(modules),
            cpu_seconds=self.cpu_seconds,
            memory_mb=self.memory_mb,
            max_output_bytes=self.max_output_bytes,
            max_code_chars=self.max_code_chars,
        )


def default_policy() -> SandboxPolicy:
    """The platform's conservative default sandbox policy (deny-by-default)."""

    return SandboxPolicy()


def _module_root(name: str) -> str:
    return name.split(".", 1)[0]


def check_code(code: str, policy: SandboxPolicy | None = None) -> list[str]:
    """Statically inspect ``code`` against ``policy``; return a list of violation reasons.

    An empty list means the static check passed (still run it under a real isolation boundary).
    A non-empty list is every reason it was rejected — surfaced together so the agent/operator
    sees all problems at once. This never executes the code; it parses the AST and looks for
    disallowed imports, forbidden names, and out-of-sandbox calls.

    Raises :class:`SyntaxError` only if ``code`` does not parse — the caller should treat that
    as a violation too (it does in :func:`enforce_code`).
    """

    pol = policy or default_policy()
    reasons: list[str] = []

    if len(code) > pol.max_code_chars:
        reasons.append(f"code exceeds {pol.max_code_chars} chars ({len(code)})")

    tree = ast.parse(code)  # SyntaxError propagates; enforce_code converts it to a violation

    for node in ast.walk(tree):
        # Imports must be on the allow-list.
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _module_root(alias.name)
                if root not in pol.allowed_imports:
                    reasons.append(f"import {alias.name!r} not in allow-list")
        elif isinstance(node, ast.ImportFrom):
            root = _module_root(node.module or "")
            if root not in pol.allowed_imports:
                reasons.append(f"from-import {node.module!r} not in allow-list")

        # Forbidden bare names (eval/exec/__import__/...).
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            reasons.append(f"use of forbidden name {node.id!r}")

        # Dotted calls that escape the sandbox (os.system, subprocess.run, ...).
        elif isinstance(node, ast.Call):
            dotted = _dotted_name(node.func)
            if dotted in _FORBIDDEN_ATTR_CALLS:
                reasons.append(f"forbidden call {dotted}()")
            # Filesystem writes via open(..., "w"/"a"/"x") unless explicitly allowed.
            if not pol.allow_filesystem_write and dotted == "open":
                mode = _open_mode(node)
                if any(m in mode for m in ("w", "a", "x", "+")):
                    reasons.append("filesystem write via open() is not allowed")

    return reasons


def enforce_code(code: str, policy: SandboxPolicy | None = None) -> None:
    """Raise :class:`SandboxViolation` if ``code`` violates ``policy`` (fail-closed).

    Unparseable code is itself a violation — never hand syntactically broken code to an
    executor on the assumption it will "just error".
    """

    try:
        reasons = check_code(code, policy)
    except SyntaxError as exc:
        raise SandboxViolation([f"code does not parse: {exc.msg}"]) from exc
    if reasons:
        raise SandboxViolation(reasons)


def _dotted_name(node: ast.AST) -> str:
    """Best-effort dotted name for a call target (``os.system`` from ``os.system(...)``)."""

    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _open_mode(call: ast.Call) -> str:
    """Extract the literal mode arg of an ``open(...)`` call, defaulting to read."""

    # Positional: open(path, mode)
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        value = call.args[1].value
        if isinstance(value, str):
            return value
    # Keyword: open(path, mode="w")
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            value = kw.value.value
            if isinstance(value, str):
                return value
    return "r"


__all__ = [
    "SandboxPolicy",
    "SandboxViolation",
    "check_code",
    "enforce_code",
    "default_policy",
]
