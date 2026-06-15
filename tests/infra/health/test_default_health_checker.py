"""Tests for the DefaultHealthChecker (production implementation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infra.health.default_health_checker import DefaultHealthChecker


def _patch_settings(monkeypatch: pytest.MonkeyPatch, messaging_enabled: bool) -> None:
    from src.shared.config import settings as settings_module
    from src.shared.config.settings import build_settings

    monkeypatch.setenv("MESSAGING_ENABLED", "true" if messaging_enabled else "false")
    settings_module.settings = build_settings()
    import src.infra.health.default_health_checker as mod

    mod.settings = settings_module.settings


@pytest.mark.asyncio
async def test_check_postgres_returns_up_on_success(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)

    class _AcquireCtx:
        async def __aenter__(self) -> object:
            return conn

        async def __aexit__(self, *args: object) -> None:
            pass

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    mocker.patch("src.infra.database.db.get_pool", new=AsyncMock(return_value=pool))

    result = await DefaultHealthChecker().check_postgres(signal=None)
    assert result.status == "up"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_postgres_returns_down_on_exception(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=RuntimeError("conn refused"))
    mocker.patch("src.infra.database.db.get_pool", new=AsyncMock(return_value=pool))

    result = await DefaultHealthChecker().check_postgres(signal=None)
    assert result.status == "down"
    assert result.error == "conn refused"


@pytest.mark.asyncio
async def test_check_redis_returns_up_when_ping_is_pong(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    client = MagicMock()
    client.ping = AsyncMock(return_value="PONG")
    mocker.patch("src.infra.redis.redis_provider.get_client", return_value=client)

    result = await DefaultHealthChecker().check_redis(signal=None)
    assert result.status == "up"


@pytest.mark.asyncio
async def test_check_redis_returns_up_when_ping_is_true(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    mocker.patch("src.infra.redis.redis_provider.get_client", return_value=client)

    result = await DefaultHealthChecker().check_redis(signal=None)
    assert result.status == "up"


@pytest.mark.asyncio
async def test_check_redis_returns_down_when_ping_returns_unexpected(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    client = MagicMock()
    client.ping = AsyncMock(return_value=b"WEIRD")
    mocker.patch("src.infra.redis.redis_provider.get_client", return_value=client)

    result = await DefaultHealthChecker().check_redis(signal=None)
    assert result.status == "down"
    assert result.error == "unexpected reply"


@pytest.mark.asyncio
async def test_check_redis_returns_down_on_exception(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    client = MagicMock()
    client.ping = AsyncMock(side_effect=ConnectionError("redis down"))
    mocker.patch("src.infra.redis.redis_provider.get_client", return_value=client)

    result = await DefaultHealthChecker().check_redis(signal=None)
    assert result.status == "down"
    assert result.error == "redis down"


@pytest.mark.asyncio
async def test_check_rabbitmq_returns_disabled_when_messaging_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_settings(monkeypatch, messaging_enabled=False)
    result = await DefaultHealthChecker().check_rabbitmq(signal=None)
    assert result.status == "disabled"


@pytest.mark.asyncio
async def test_check_rabbitmq_returns_up_when_check_passes(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    _patch_settings(monkeypatch, messaging_enabled=True)
    fake = MagicMock()
    fake.check = MagicMock(return_value=True)
    mocker.patch(
        "src.infra.health.default_health_checker.rabbitmq_provider.messaging_provider",
        fake,
    )
    result = await DefaultHealthChecker().check_rabbitmq(signal=None)
    assert result.status == "up"


@pytest.mark.asyncio
async def test_check_rabbitmq_returns_down_when_check_returns_false(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    _patch_settings(monkeypatch, messaging_enabled=True)
    fake = MagicMock()
    fake.check = MagicMock(return_value=False)
    mocker.patch(
        "src.infra.health.default_health_checker.rabbitmq_provider.messaging_provider",
        fake,
    )
    result = await DefaultHealthChecker().check_rabbitmq(signal=None)
    assert result.status == "down"
    assert result.error == "connection closed"


@pytest.mark.asyncio
async def test_check_rabbitmq_returns_down_on_exception(
    monkeypatch: pytest.MonkeyPatch, mocker: pytest.MockerFixture
) -> None:
    _patch_settings(monkeypatch, messaging_enabled=True)
    fake = MagicMock()
    fake.check = MagicMock(side_effect=ConnectionError("rabbit down"))
    mocker.patch(
        "src.infra.health.default_health_checker.rabbitmq_provider.messaging_provider",
        fake,
    )
    result = await DefaultHealthChecker().check_rabbitmq(signal=None)
    assert result.status == "down"
    assert result.error == "rabbit down"
