"""Domain-error → HTTP translation (Ch 25, 28).

The domain raises its own exceptions (``app.domain.errors``), never ``HTTPException`` — that is
what keeps it web-free. The single seam that turns those into HTTP responses lives here, mounted
by the app factory. Add a mapping when you add a domain error; routes stay clean because they
just let the domain error propagate.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import (
    ApprovalRequiredError,
    DomainError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    TenantAccessError,
)

# Map each domain error class to an HTTP status code.
_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    TenantAccessError: status.HTTP_403_FORBIDDEN,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    ApprovalRequiredError: status.HTTP_202_ACCEPTED,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Install the domain-error and catch-all handlers on the app."""

    @app.exception_handler(DomainError)
    async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        code = _STATUS_BY_ERROR.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=code, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        # Last line of defense: never leak a stack trace to a client.
        import logging

        logging.getLogger("agentic-platform").exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )
