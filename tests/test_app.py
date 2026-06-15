"""Tests for the application bootstrap."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src import app as app_module
from src.app import cleanup, start


@pytest.fixture
def mock_setup_logging(mocker: pytest.MockerFixture) -> MagicMock:
    return mocker.patch("src.app.setup_logging")


@pytest.fixture
def mock_redis(mocker: pytest.MockerFixture) -> MagicMock:
    return mocker.patch("src.app.redis_provider.get_client", return_value=MagicMock())


@pytest.fixture
def mock_db_pool(mocker: pytest.MockerFixture) -> MagicMock:
    pool = mocker.patch("src.app.database.get_pool", new=AsyncMock(return_value=MagicMock()))
    return pool


@pytest.fixture
def mock_rabbit(mocker: pytest.MockerFixture) -> MagicMock:
    return mocker.patch(
        "src.app.messaging_provider.connect", new=AsyncMock(return_value=None)
    )


@pytest.fixture
def mock_register_jobs(mocker: pytest.MockerFixture) -> MagicMock:
    scheduler = MagicMock(name="scheduler")
    scheduler.start = MagicMock()
    scheduler.list_jobs = MagicMock(return_value=[])
    return mocker.patch("src.app.register_jobs", return_value=scheduler)


@pytest.fixture
def mock_shutdown_handlers(mocker: pytest.MockerFixture) -> MagicMock:
    return mocker.patch("src.app.register_shutdown_handlers")


@pytest.mark.asyncio
async def test_start_initializes_logging(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
) -> None:
    await start()
    mock_setup_logging.assert_called_once()


@pytest.mark.asyncio
async def test_start_initializes_redis_and_db(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
) -> None:
    await start()
    mock_redis.assert_called_once()
    mock_db_pool.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_connects_rabbit_when_enabled(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "true")
    from src.shared.config import settings as settings_module

    settings_module.settings = app_module.__dict__  # placeholder, real rebuild below
    from src.shared.config.settings import build_settings

    settings_module.settings = build_settings()
    app_module.settings = settings_module.settings

    await start()
    mock_rabbit.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_skips_rabbit_when_disabled(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "false")
    from src.shared.config.settings import build_settings

    app_module.settings = build_settings()

    await start()
    mock_rabbit.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_tolerates_rabbit_connection_failure(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MESSAGING_ENABLED", "true")
    from src.shared.config.settings import build_settings

    app_module.settings = build_settings()
    mock_rabbit.side_effect = ConnectionError("rabbit down")

    await start()
    mock_rabbit.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_starts_scheduler(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
) -> None:
    await start()
    mock_register_jobs.assert_called_once()
    mock_register_jobs.return_value.start.assert_called_once()


@pytest.mark.asyncio
async def test_start_registers_shutdown_handlers(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
) -> None:
    await start()
    mock_shutdown_handlers.assert_called_once()
    # The handler passed should be `cleanup`
    assert mock_shutdown_handlers.call_args.args[0] is cleanup


@pytest.mark.asyncio
async def test_start_returns_scheduler(
    mock_setup_logging: MagicMock,
    mock_redis: MagicMock,
    mock_db_pool: MagicMock,
    mock_rabbit: MagicMock,
    mock_register_jobs: MagicMock,
    mock_shutdown_handlers: MagicMock,
) -> None:
    result = await start()
    assert result is mock_register_jobs.return_value


@pytest.mark.asyncio
async def test_cleanup_closes_rabbit_redis_db_in_order(
    mocker: pytest.MockerFixture,
) -> None:
    call_order: list[str] = []

    async def rabbit_disconnect() -> None:
        call_order.append("rabbit")

    async def redis_close() -> None:
        call_order.append("redis")

    async def db_close_pool() -> None:
        call_order.append("db")

    mocker.patch("src.app.messaging_provider.disconnect", new=AsyncMock(side_effect=rabbit_disconnect))
    mocker.patch("src.app.redis_provider.close", new=AsyncMock(side_effect=redis_close))
    mocker.patch("src.app.database.close_pool", new=AsyncMock(side_effect=db_close_pool))

    await cleanup()
    assert call_order == ["rabbit", "redis", "db"]
