"""Tests for the async Redis singleton."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.infra.redis import redis_provider


class _FakeClient:
    def __init__(self) -> None:
        self.aclose_calls = 0

    async def aclose(self) -> None:
        self.aclose_calls += 1


@pytest.fixture(autouse=True)
def _reset_and_mock(mocker: pytest.MockerFixture) -> None:
    """Mock redis.Redis and redis.from_url, then reset the singleton."""
    fake = _FakeClient()
    mocker.patch("src.infra.redis.redis_provider.redis.Redis", return_value=fake)
    mocker.patch("src.infra.redis.redis_provider.redis.from_url", return_value=fake)
    redis_provider.reset()
    yield
    redis_provider.reset()


def test_get_client_returns_singleton() -> None:
    a = redis_provider.get_client()
    b = redis_provider.get_client()
    assert a is b


def test_get_client_uses_from_url_when_redis_host_is_url(
    mocker: pytest.MockerFixture,
) -> None:
    from_url_mock = mocker.patch(
        "src.infra.redis.redis_provider.redis.from_url", return_value=_FakeClient()
    )
    redis_provider.reset()

    fake_settings = MagicMock()
    fake_settings.redis_host = "redis://example.com:6379/0"
    fake_settings.redis_password = "secret"
    fake_settings.redis_db = 0
    fake_settings.redis_command_timeout_s = 5.0
    mocker.patch("src.infra.redis.redis_provider.settings", fake_settings)

    redis_provider.get_client()
    from_url_mock.assert_called_once()
    call_kwargs = from_url_mock.call_args.kwargs
    assert "host" not in from_url_mock.call_args.args
    assert call_kwargs["db"] == 0


def test_get_client_uses_redis_constructor_when_redis_host_is_plain(
    mocker: pytest.MockerFixture,
) -> None:
    redis_ctor_mock = mocker.patch(
        "src.infra.redis.redis_provider.redis.Redis", return_value=_FakeClient()
    )
    redis_provider.reset()

    fake_settings = MagicMock()
    fake_settings.redis_host = "127.0.0.1"
    fake_settings.redis_port = 6380
    fake_settings.redis_password = "secret"
    fake_settings.redis_db = 0
    fake_settings.redis_command_timeout_s = 5.0
    mocker.patch("src.infra.redis.redis_provider.settings", fake_settings)

    redis_provider.get_client()
    redis_ctor_mock.assert_called_once()
    call_kwargs = redis_ctor_mock.call_args.kwargs
    assert call_kwargs["host"] == "127.0.0.1"
    assert call_kwargs["port"] == 6380
    assert call_kwargs["db"] == 0


def test_get_client_uses_rediss_scheme(mocker: pytest.MockerFixture) -> None:
    from_url_mock = mocker.patch(
        "src.infra.redis.redis_provider.redis.from_url", return_value=_FakeClient()
    )
    redis_provider.reset()

    fake_settings = MagicMock()
    fake_settings.redis_host = "rediss://secure.example.com:6380/0"
    fake_settings.redis_password = "secret"
    fake_settings.redis_db = 0
    fake_settings.redis_command_timeout_s = 5.0
    mocker.patch("src.infra.redis.redis_provider.settings", fake_settings)

    redis_provider.get_client()
    from_url_mock.assert_called_once()


def test_get_client_uses_empty_password_as_none(
    mocker: pytest.MockerFixture,
) -> None:
    redis_ctor_mock = mocker.patch(
        "src.infra.redis.redis_provider.redis.Redis", return_value=_FakeClient()
    )
    redis_provider.reset()

    fake_settings = MagicMock()
    fake_settings.redis_host = "127.0.0.1"
    fake_settings.redis_port = 6379
    fake_settings.redis_password = ""
    fake_settings.redis_db = 0
    fake_settings.redis_command_timeout_s = 5.0
    mocker.patch("src.infra.redis.redis_provider.settings", fake_settings)

    redis_provider.get_client()
    assert redis_ctor_mock.call_args.kwargs["password"] is None


@pytest.mark.asyncio
async def test_close_closes_existing_client() -> None:
    client = redis_provider.get_client()
    await redis_provider.close()
    assert isinstance(client, _FakeClient)
    assert client.aclose_calls == 1
    assert redis_provider._client is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_close_is_noop_when_client_is_none() -> None:
    assert redis_provider._client is None  # noqa: SLF001
    await redis_provider.close()
    assert redis_provider._client is None  # noqa: SLF001


def test_reset_clears_client_reference() -> None:
    redis_provider._client = "fake"  # type: ignore[assignment]  # noqa: SLF001
    redis_provider.reset()
    assert redis_provider._client is None  # noqa: SLF001


def test_get_client_caches_after_first_construction(mocker: pytest.MockerFixture) -> None:
    redis_ctor_mock = mocker.patch(
        "src.infra.redis.redis_provider.redis.Redis", return_value=_FakeClient()
    )
    redis_provider.reset()
    redis_provider.get_client()
    redis_provider.get_client()
    redis_provider.get_client()
    assert redis_ctor_mock.call_count == 1


def _silence_pytest(_: Any) -> None:
    pass
