"""Tool-permission tiers (Ch 41) — risk-tiered authorization for tool calls.

Every tool the agent can call is assigned a **risk tier**. The tier — not a prompt, not the
model's judgement — decides what happens when the agent tries to use it: run it, require a
human approval first, or refuse. This is the "structure enforces" half of the safety story:
the model can *ask* to delete a customer, but the tier table is what actually lets or stops it.

The four tiers (least → most privileged):

============ ====================================================== ========================
Tier         Examples                                               Default disposition
============ ====================================================== ========================
READ         search_docs, get_ticket, list_orders                   allow
WRITE        create_ticket, send_email, update_record               allow (audited)
SENSITIVE    issue_refund, delete_record, run_code, charge_card     require human approval
ADMIN        rotate_keys, change_permissions, drop_table            deny unless a privileged
                                                                     principal explicitly allows
============ ====================================================== ========================

The disposition also depends on *who* is acting (a :class:`Principal`'s ``max_tier``), so the
same tool is callable by a privileged operator and gated for an anonymous end-user. The
decision is data, not control flow, so it is unit-testable and auditable — every call to
:meth:`ToolPermissionRegistry.authorize` returns a :class:`AccessDecision` you can write to
``security.audit``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class PermissionError_(RuntimeError):
    """Raised when a tool call is denied by the permission tier policy.

    Named with a trailing underscore so it never shadows the builtin :class:`PermissionError`.
    """


class PermissionTier(IntEnum):
    """A tool's risk tier. ``IntEnum`` so tiers compare/order naturally (READ < ADMIN)."""

    READ = 0
    WRITE = 1
    SENSITIVE = 2
    ADMIN = 3

    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: "PermissionTier | str | int") -> "PermissionTier":
        """Coerce a name (``"sensitive"``), an int, or a tier into a :class:`PermissionTier`."""

        if isinstance(value, PermissionTier):
            return value
        if isinstance(value, int):
            return cls(value)
        try:
            return cls[str(value).strip().upper()]
        except KeyError as exc:
            raise ValueError(f"unknown permission tier {value!r}") from exc


class Outcome(str, Enum):
    """What the policy decided for one tool call."""

    ALLOW = "allow"  # run it now
    REQUIRE_APPROVAL = "require_approval"  # hold for a human (the approval gate)
    DENY = "deny"  # refuse outright

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Principal:
    """Who is acting. ``max_tier`` is the highest tier this principal may invoke directly.

    An anonymous end-user defaults to READ; a support operator to WRITE; an admin to ADMIN. A
    tool at or below ``max_tier`` *and* not flagged ``requires_approval`` runs immediately;
    above it, the call is denied (or, for one tier up, gated for approval — see
    :meth:`ToolPermissionRegistry.authorize`).
    """

    id: str
    max_tier: PermissionTier = PermissionTier.READ
    roles: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def end_user(id: str = "anonymous") -> "Principal":
        return Principal(id=id, max_tier=PermissionTier.READ, roles=("end_user",))

    @staticmethod
    def operator(id: str) -> "Principal":
        return Principal(id=id, max_tier=PermissionTier.WRITE, roles=("operator",))

    @staticmethod
    def admin(id: str) -> "Principal":
        return Principal(id=id, max_tier=PermissionTier.ADMIN, roles=("admin",))


@dataclass(frozen=True)
class ToolPermission:
    """The declared risk of one tool.

    ``tier`` is the floor of authority needed to run it. ``requires_approval`` forces a
    human-in-the-loop hold even when the principal is otherwise allowed (the default for
    SENSITIVE and above) — this is the flag ``agents/approvals.py`` reads to decide when to
    pause a run.
    """

    name: str
    tier: PermissionTier
    requires_approval: bool = False
    description: str = ""

    @staticmethod
    def of(
        name: str,
        tier: PermissionTier | str | int,
        *,
        requires_approval: bool | None = None,
        description: str = "",
    ) -> "ToolPermission":
        t = PermissionTier.parse(tier)
        # SENSITIVE/ADMIN default to needing approval unless explicitly overridden.
        needs = requires_approval if requires_approval is not None else t >= PermissionTier.SENSITIVE
        return ToolPermission(
            name=name,
            tier=t,
            requires_approval=needs,
            description=description,
        )


@dataclass(frozen=True)
class AccessDecision:
    """The result of authorizing a tool call. Log this to ``security.audit``."""

    tool: str
    principal_id: str
    outcome: Outcome
    tier: PermissionTier
    reason: str

    @property
    def allowed(self) -> bool:
        return self.outcome is Outcome.ALLOW

    @property
    def needs_approval(self) -> bool:
        return self.outcome is Outcome.REQUIRE_APPROVAL


class ToolPermissionRegistry:
    """The tier table + the authorization rule.

    Register each tool's :class:`ToolPermission` once (at startup, next to where the tool is
    defined), then call :meth:`authorize` on every tool invocation. An *unregistered* tool is
    denied by default — least privilege: a tool nobody classified cannot run.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolPermission] = {}

    def register(self, perm: ToolPermission) -> ToolPermission:
        """Declare a tool's permission. Re-registering replaces the prior declaration."""

        self._tools[perm.name] = perm
        return perm

    def register_many(self, perms: list[ToolPermission]) -> None:
        for p in perms:
            self.register(p)

    def get(self, tool: str) -> ToolPermission | None:
        return self._tools.get(tool)

    def authorize(self, tool: str, principal: Principal) -> AccessDecision:
        """Decide what happens when ``principal`` invokes ``tool``.

        Rules (deny-by-default):

        * Unknown tool → DENY (nobody classified it).
        * Tool tier ≤ principal.max_tier and no approval flag → ALLOW.
        * Approval flag set, or tool tier is exactly one step above the principal → hold for a
          human (REQUIRE_APPROVAL).
        * Tool tier more than one step above the principal → DENY.
        """

        perm = self._tools.get(tool)
        if perm is None:
            return AccessDecision(
                tool=tool,
                principal_id=principal.id,
                outcome=Outcome.DENY,
                tier=PermissionTier.ADMIN,
                reason="tool is not registered (deny by default)",
            )

        within_authority = perm.tier <= principal.max_tier
        one_step_above = int(perm.tier) == int(principal.max_tier) + 1

        if within_authority and not perm.requires_approval:
            return AccessDecision(
                tool=tool,
                principal_id=principal.id,
                outcome=Outcome.ALLOW,
                tier=perm.tier,
                reason=f"{perm.tier} <= {principal.max_tier} (principal authority)",
            )

        if (within_authority and perm.requires_approval) or one_step_above:
            return AccessDecision(
                tool=tool,
                principal_id=principal.id,
                outcome=Outcome.REQUIRE_APPROVAL,
                tier=perm.tier,
                reason=(
                    "tool requires human approval"
                    if perm.requires_approval
                    else f"{perm.tier} is one tier above {principal.max_tier}"
                ),
            )

        return AccessDecision(
            tool=tool,
            principal_id=principal.id,
            outcome=Outcome.DENY,
            tier=perm.tier,
            reason=f"{perm.tier} exceeds {principal.max_tier} by more than one tier",
        )

    def enforce(self, tool: str, principal: Principal) -> AccessDecision:
        """Authorize and raise :class:`PermissionError_` on a hard DENY.

        REQUIRE_APPROVAL is *not* an error — it is returned so the caller (the approval gate)
        can hold the run. Only an outright DENY raises.
        """

        decision = self.authorize(tool, principal)
        if decision.outcome is Outcome.DENY:
            raise PermissionError_(
                f"tool {tool!r} denied for {principal.id!r}: {decision.reason}"
            )
        return decision


def default_registry() -> ToolPermissionRegistry:
    """A registry pre-loaded with the platform's standard tools and their tiers.

    Adapt this to your toolset — the *shape* (every tool classified, deny-by-default for the
    rest) is the lesson, not this exact list.
    """

    reg = ToolPermissionRegistry()
    reg.register_many(
        [
            ToolPermission.of("search_docs", PermissionTier.READ, description="RAG search over the corpus"),
            ToolPermission.of("get_ticket", PermissionTier.READ, description="Read a support ticket"),
            ToolPermission.of("list_orders", PermissionTier.READ, description="List a customer's orders"),
            ToolPermission.of("create_ticket", PermissionTier.WRITE, description="Open a support ticket"),
            ToolPermission.of("send_email", PermissionTier.WRITE, description="Send a templated email"),
            ToolPermission.of("issue_refund", PermissionTier.SENSITIVE, description="Refund a charge"),
            ToolPermission.of("run_code", PermissionTier.SENSITIVE, description="Execute code in the sandbox"),
            ToolPermission.of("delete_record", PermissionTier.SENSITIVE, description="Hard-delete a record"),
            ToolPermission.of("rotate_keys", PermissionTier.ADMIN, description="Rotate provider keys"),
            ToolPermission.of("change_permissions", PermissionTier.ADMIN, description="Edit the tier table"),
        ]
    )
    return reg


# Process-wide default registry, lazily created so importing the module is cheap.
_REGISTRY: ToolPermissionRegistry | None = None


def permission_registry() -> ToolPermissionRegistry:
    """The process-wide default :class:`ToolPermissionRegistry` (created on first use)."""

    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = default_registry()
    return _REGISTRY


__all__ = [
    "PermissionTier",
    "Outcome",
    "Principal",
    "ToolPermission",
    "AccessDecision",
    "ToolPermissionRegistry",
    "PermissionError_",
    "default_registry",
    "permission_registry",
]
