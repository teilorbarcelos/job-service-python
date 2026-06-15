"""Tests for the AppError hierarchy."""

from __future__ import annotations

import pytest

from src.shared.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_app_error_stores_message() -> None:
    e = AppError("boom")
    assert e.message == "boom"
    assert str(e) == "boom"


def test_app_error_is_exception_subclass() -> None:
    assert issubclass(AppError, Exception)


def test_not_found_error_inherits_app_error() -> None:
    e = NotFoundError("missing")
    assert isinstance(e, AppError)
    assert e.message == "missing"


def test_conflict_error_inherits_app_error() -> None:
    assert isinstance(ConflictError("dup"), AppError)


def test_validation_error_inherits_app_error() -> None:
    assert isinstance(ValidationError("bad"), AppError)


def test_unauthorized_error_inherits_app_error() -> None:
    assert isinstance(UnauthorizedError("no auth"), AppError)


def test_forbidden_error_inherits_app_error() -> None:
    assert isinstance(ForbiddenError("nope"), AppError)


@pytest.mark.parametrize(
    "cls",
    [NotFoundError, ConflictError, ValidationError, UnauthorizedError, ForbiddenError],
)
def test_all_subclasses_default_message(cls: type[AppError]) -> None:
    e = cls()
    assert e.message == cls.__name__
    assert isinstance(e, AppError)
