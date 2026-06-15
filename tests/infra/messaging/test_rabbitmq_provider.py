"""Tests for the RabbitMQ provider."""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.infra.messaging import rabbitmq_provider
from src.infra.messaging.rabbitmq_provider import RabbitMQProvider
from src.shared.config import settings as settings_module
from src.shared.config.settings import build_settings


class _FakeChannel:
    def __init__(self) -> None:
        self.closed = False
        self.published: list[tuple[Any, str]] = []
        self.set_qos_called = False

    async def close(self) -> None:
        self.closed = True

    async def set_qos(self, prefetch_count: int) -> None:
        self.set_qos_called = True
        assert prefetch_count == 1

    @property
    def default_exchange(self) -> _FakeExchange:
        return _FakeExchange(self)


class _FakeExchange:
    def __init__(self, channel: _FakeChannel) -> None:
        self._channel = channel

    async def publish(self, message: Any, routing_key: str) -> None:
        self._channel.published.append((message, routing_key))


class _FakeConnection:
    def __init__(self, channel: _FakeChannel, *, closed: bool = False) -> None:
        self._channel = channel
        self._closed = closed

    async def channel(self) -> _FakeChannel:
        return self._channel

    async def close(self) -> None:
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


def _set_messaging(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    """Rebuild settings and replace the module-level reference.

    The provider reads `settings` at call time, so swapping the module
    attribute is enough to flip behavior for the duration of the test.
    """
    monkeypatch.setenv("MESSAGING_ENABLED", "true" if enabled else "false")
    rabbitmq_provider.settings = build_settings()  # type: ignore[attr-defined]
    settings_module.settings = rabbitmq_provider.settings  # type: ignore[attr-defined]


@pytest.fixture
def fresh_provider() -> RabbitMQProvider:
    return RabbitMQProvider()


@pytest.fixture
def connected_provider() -> tuple[RabbitMQProvider, _FakeChannel, _FakeConnection]:
    channel = _FakeChannel()
    connection = _FakeConnection(channel)
    provider = RabbitMQProvider()
    provider._connection = connection  # noqa: SLF001
    provider._channel = channel  # noqa: SLF001
    return provider, channel, connection


def test_check_returns_false_when_not_connected(fresh_provider: RabbitMQProvider) -> None:
    assert fresh_provider.check() is False


def test_check_returns_true_when_connected_and_open(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
) -> None:
    provider, _, _ = connected_provider
    assert provider.check() is True


@pytest.mark.asyncio
async def test_connect_is_noop_when_messaging_disabled(
    fresh_provider: RabbitMQProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_messaging(monkeypatch, enabled=False)
    await fresh_provider.connect()
    assert fresh_provider._connection is None  # noqa: SLF001
    assert fresh_provider._channel is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_connect_opens_connection_when_enabled(
    fresh_provider: RabbitMQProvider,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest.MockerFixture,
) -> None:
    _set_messaging(monkeypatch, enabled=True)
    channel = _FakeChannel()
    connection = _FakeConnection(channel)
    connect_robust = mocker.patch(
        "src.infra.messaging.rabbitmq_provider.aio_pika.connect_robust",
        new=mocker.AsyncMock(return_value=connection),
    )

    await fresh_provider.connect()

    connect_robust.assert_awaited_once()
    assert fresh_provider._connection is connection  # noqa: SLF001
    assert fresh_provider._channel is channel  # noqa: SLF001
    assert channel.set_qos_called is True


@pytest.mark.asyncio
async def test_publish_is_noop_when_messaging_disabled(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, channel, _ = connected_provider
    _set_messaging(monkeypatch, enabled=False)
    await provider.publish("q", {"x": 1})
    assert channel.published == []


@pytest.mark.asyncio
async def test_publish_raises_when_enabled_but_channel_not_initialized(
    fresh_provider: RabbitMQProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_messaging(monkeypatch, enabled=True)
    with pytest.raises(RuntimeError, match="RabbitMQ channel not initialized"):
        await fresh_provider.publish("q", {"x": 1})


@pytest.mark.asyncio
async def test_publish_sends_message_with_persistent_delivery(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, channel, _ = connected_provider
    _set_messaging(monkeypatch, enabled=True)
    payload = {"hello": "world", "count": 42}
    await provider.publish("my-queue", payload)
    assert len(channel.published) == 1
    message, routing_key = channel.published[0]
    assert routing_key == "my-queue"
    assert json.loads(message.body.decode()) == payload
    assert message.delivery_mode.value == 2  # PERSISTENT


@pytest.mark.asyncio
async def test_disconnect_closes_channel_and_connection(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
) -> None:
    provider, channel, connection = connected_provider
    await provider.disconnect()
    assert channel.closed is True
    assert connection.is_closed is True
    assert provider._connection is None  # noqa: SLF001
    assert provider._channel is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_disconnect_is_noop_when_not_connected(
    fresh_provider: RabbitMQProvider,
) -> None:
    await fresh_provider.disconnect()
    assert fresh_provider._connection is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_disconnect_swallows_channel_close_error(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
) -> None:
    provider, channel, connection = connected_provider

    async def boom() -> None:
        raise RuntimeError("channel fail")

    channel.close = boom  # type: ignore[method-assign]
    await provider.disconnect()
    assert connection.is_closed is True


@pytest.mark.asyncio
async def test_disconnect_swallows_connection_close_error(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
) -> None:
    provider, _, connection = connected_provider

    async def boom() -> None:
        raise RuntimeError("conn fail")

    connection.close = boom  # type: ignore[method-assign]
    await provider.disconnect()
    assert provider._connection is None  # noqa: SLF001


def test_singleton_instance_is_module_global() -> None:
    assert isinstance(rabbitmq_provider.rabbitmq_provider, RabbitMQProvider)


def test_publish_marks_connection_closed_after_disconnect(
    connected_provider: tuple[RabbitMQProvider, _FakeChannel, _FakeConnection],
) -> None:
    provider, _, connection = connected_provider
    assert provider.check() is True
    connection._closed = True
    assert provider.check() is False
