import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.infra.messaging.rabbitmq_provider import RabbitMQProvider


@pytest.fixture
def provider():
    return RabbitMQProvider()


@pytest.mark.asyncio
async def test_declare_exchange(provider):
    mock_exchange = AsyncMock()
    provider._channel = AsyncMock()
    provider._channel.declare_exchange = AsyncMock(return_value=mock_exchange)
    provider._channel.is_closed = False

    result = await provider.declare_exchange("test.ex", "topic")
    assert result == mock_exchange
    assert "test.ex" in provider._exchanges


@pytest.mark.asyncio
async def test_declare_queue_with_dlq(provider):
    mock_queue = AsyncMock()
    provider._channel = AsyncMock()
    provider._channel.declare_queue = AsyncMock(return_value=mock_queue)
    provider._channel.is_closed = False

    result = await provider.declare_queue("test.q", dlq="dlx", dlq_routing_key="drk")
    assert result == mock_queue
    assert "test.q" in provider._queues


@pytest.mark.asyncio
async def test_bind_success(provider):
    mock_queue = AsyncMock()
    mock_exchange = MagicMock()
    provider._queues["q"] = mock_queue
    provider._exchanges["ex"] = mock_exchange
    provider._channel = AsyncMock()
    provider._channel.is_closed = False

    await provider.bind("q", "ex", "rk")
    mock_queue.bind.assert_called_once_with(mock_exchange, routing_key="rk")


@pytest.mark.asyncio
async def test_bind_fails_when_missing(provider):
    provider._channel = AsyncMock()
    provider._channel.is_closed = False
    with pytest.raises(RuntimeError, match="not declared"):
        await provider.bind("nonexistent", "ex", "rk")
    provider._queues.clear()


@pytest.mark.asyncio
async def test_ensure_channel_when_closed(provider):
    with patch.object(provider, "connect", AsyncMock()) as mock_connect:
        provider._channel = AsyncMock()
        provider._channel.is_closed = True
        await provider._ensure_channel()
        mock_connect.assert_called_once()


@pytest.mark.asyncio
async def test_start_consumers_disabled(provider):
    with patch.object(provider, "_run_consumer", AsyncMock()):
        with patch("src.infra.messaging.rabbitmq_provider.settings.messaging_enabled", False):
            await provider.start_consumers()
            assert len(provider._consumer_tasks) == 0
