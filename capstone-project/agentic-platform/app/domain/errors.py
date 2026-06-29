"""Domain exception hierarchy (Ch 28).

The domain raises *its own* exceptions — never ``HTTPException``. That keeps ``domain/`` free
of any web dependency (the cardinal rule) and lets the same logic run inside a Celery worker,
where HTTP status codes are meaningless. The ``api/`` layer maps these to responses (see
``app.api.errors``); the worker layer maps them to retry/dead-letter decisions.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all expected, business-level failures."""


class EntityNotFoundError(DomainError):
    """A requested entity does not exist (or is not visible to this tenant)."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} '{entity_id}' not found.")


class TenantAccessError(DomainError):
    """A caller tried to touch an entity belonging to another tenant."""

    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"Access to {entity} '{entity_id}' is denied for this tenant.")


class InvalidStateTransitionError(DomainError):
    """An attempt to move an entity through an illegal state transition."""

    def __init__(self, entity: str, frm: str, to: str) -> None:
        self.entity = entity
        self.frm = frm
        self.to = to
        super().__init__(f"{entity} cannot move from '{frm}' to '{to}'.")


class ApprovalRequiredError(DomainError):
    """A run paused awaiting a human approval before a risky tool may execute (Ch 20)."""

    def __init__(self, run_id: str, tool_name: str) -> None:
        self.run_id = run_id
        self.tool_name = tool_name
        super().__init__(
            f"Run '{run_id}' is paused: tool '{tool_name}' requires human approval."
        )
