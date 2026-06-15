"""General-purpose exception hierarchy for the job runner.

These are domain-level errors that any job may raise when it
catches a recoverable business-logic problem (validation, conflict,
not-found, etc). The BaseJob.run() method catches `Exception`
and converts it into a JobResult with status="error" + the message.

By having named classes instead of bare ValueError/RuntimeError,
log aggregation and alerting can distinguish error categories
without parsing message strings.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all domain errors raised by jobs."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__


class NotFoundError(AppError):
    """Raised when an expected resource does not exist."""


class ConflictError(AppError):
    """Raised when an operation collides with current state (e.g. duplicate)."""


class ValidationError(AppError):
    """Raised when input data fails business validation."""


class UnauthorizedError(AppError):
    """Raised when credentials are missing or invalid."""


class ForbiddenError(AppError):
    """Raised when the caller is authenticated but lacks permission."""
