"""Tests for the asyncpg pool singleton and DSN normalization."""

from __future__ import annotations

import pytest

from src.infra.database import db


@pytest.fixture(autouse=True)
def mock_create_pool(mocker: pytest.MockerFixture) -> None:
    """Patch asyncpg.create_pool so no test ever hits a real database."""
    pool = mocker.MagicMock(name="asyncpg_pool")
    pool.close = mocker.AsyncMock()
    mocker.patch(
        "src.infra.database.db.asyncpg.create_pool",
        new=mocker.AsyncMock(return_value=pool),
    )
    db.reset()
    yield
    db.reset()


def test_normalize_dsn_strips_asyncpg_suffix() -> None:
    assert (
        db._normalize_dsn("postgresql+asyncpg://user:pass@host:5432/db")  # noqa: SLF001
        == "postgresql://user:pass@host:5432/db"
    )


def test_normalize_dsn_keeps_plain_postgresql() -> None:
    assert (
        db._normalize_dsn("postgresql://user:pass@host:5432/db")  # noqa: SLF001
        == "postgresql://user:pass@host:5432/db"
    )


def test_normalize_dsn_keeps_postgres_scheme() -> None:
    assert (
        db._normalize_dsn("postgres://user:pass@host:5432/db")  # noqa: SLF001
        == "postgres://user:pass@host:5432/db"
    )


@pytest.mark.asyncio
async def test_get_pool_returns_singleton() -> None:
    a = await db.get_pool()
    b = await db.get_pool()
    assert a is b


@pytest.mark.asyncio
async def test_get_pool_creates_pool_on_first_call() -> None:
    assert db._pool is None  # noqa: SLF001
    pool = await db.get_pool()
    assert pool is not None
    assert db._pool is pool  # noqa: SLF001


@pytest.mark.asyncio
async def test_get_pool_passes_settings_to_create_pool(mocker: pytest.MockerFixture) -> None:
    pool = mocker.MagicMock(name="pool")
    pool.close = mocker.AsyncMock()
    create_mock = mocker.patch(
        "src.infra.database.db.asyncpg.create_pool",
        new=mocker.AsyncMock(return_value=pool),
    )
    db.reset()

    await db.get_pool()

    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["min_size"] == 2
    assert call_kwargs["max_size"] == settings_for_test().database_pool_max
    assert call_kwargs["command_timeout"] == settings_for_test().database_command_timeout_s
    assert "dsn" in call_kwargs


def test_reset_clears_pool_reference() -> None:
    db._pool = "fake"  # type: ignore[assignment]  # noqa: SLF001
    db.reset()
    assert db._pool is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_close_pool_closes_existing_pool() -> None:
    pool = await db.get_pool()
    assert db._pool is pool  # noqa: SLF001
    await db.close_pool()
    pool.close.assert_awaited_once()
    assert db._pool is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_close_pool_is_noop_when_pool_is_none() -> None:
    assert db._pool is None  # noqa: SLF001
    await db.close_pool()
    assert db._pool is None  # noqa: SLF001


def settings_for_test():
    """Helper to read current settings for assertion."""
    from src.shared.config.settings import build_settings

    return build_settings()
