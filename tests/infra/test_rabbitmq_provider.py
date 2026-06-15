import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.infra.messaging.rabbitmq_provider import RabbitMQProvider
from src.shared.config.settings import settings


@pytest.fixture
def rabbit_provider():
    return RabbitMQProvider()


@pytest.mark.asyncio
async def test_connect_disabled(rabbit_provider):
    with patch.object(settings, "messaging_enabled", False):
        await rabbit_provider.connect()
        assert rabbit_provider._connection is None


@pytest.mark.asyncio
async def test_connect_enabled(rabbit_provider):
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connection.is_closed = False

    with patch("aio_pika.connect_robust", AsyncMock(return_value=mock_connection)) as mock_connect:
        with patch.object(settings, "messaging_enabled", True):
            mock_connection.channel = AsyncMock(return_value=mock_channel)
            await rabbit_provider.connect()
            mock_connect.assert_called_once_with(settings.rabbit_url, timeout=10)
            assert rabbit_provider._connection == mock_connection
            assert rabbit_provider._channel == mock_channel


@pytest.mark.asyncio
async def test_publish_disabled(rabbit_provider):
    with patch.object(settings, "messaging_enabled", False):
        await rabbit_provider.publish("test_queue", {"msg": "hello"})


@pytest.mark.asyncio
async def test_publish_enabled(rabbit_provider):
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_channel.default_exchange = mock_exchange
    rabbit_provider._channel = mock_channel

    with patch.object(settings, "messaging_enabled", True):
        await rabbit_provider.publish("test_queue", {"msg": "hello"})
        mock_exchange.publish.assert_called_once()


@pytest.mark.asyncio
async def test_publish_reconnects_if_needed(rabbit_provider):
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_connection.is_closed = False

    with patch("aio_pika.connect_robust", AsyncMock(return_value=mock_connection)):
        with patch.object(settings, "messaging_enabled", True):
            mock_connection.channel = AsyncMock(return_value=mock_channel)
            await rabbit_provider.publish("test_queue", {"msg": "hello"})
            assert rabbit_provider._channel == mock_channel


@pytest.mark.asyncio
async def test_disconnect(rabbit_provider):
    mock_connection = AsyncMock()
    mock_connection.is_closed = False
    mock_channel = AsyncMock()
    mock_channel.is_closed = False
    rabbit_provider._connection = mock_connection
    rabbit_provider._channel = mock_channel
    await rabbit_provider.disconnect()
    mock_channel.close.assert_called_once()
    mock_connection.close.assert_called_once()


@pytest.mark.asyncio
async def test_publish_error_no_channel(rabbit_provider):
    with patch.object(settings, "messaging_enabled", True):
        with patch.object(rabbit_provider, "connect", AsyncMock()):
            rabbit_provider._channel = None
            with pytest.raises(RuntimeError, match="RabbitMQ channel not initialized"):
                await rabbit_provider.publish("test_queue", {})


@pytest.mark.asyncio
async def test_subscribe_disabled(rabbit_provider):
    with patch.object(settings, "messaging_enabled", False):
        await rabbit_provider.subscribe("test_queue", AsyncMock())


@pytest.mark.asyncio
async def test_subscribe_enabled(rabbit_provider):
    mock_channel = AsyncMock()
    mock_queue = MagicMock()
    rabbit_provider._channel = mock_channel
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

    mock_iter_ctx = MagicMock()
    mock_iter_ctx.__aenter__ = AsyncMock()
    mock_iter_ctx.__aexit__ = AsyncMock()
    mock_queue.iterator = MagicMock(return_value=mock_iter_ctx)

    rabbit_provider._queues["test_queue"] = mock_queue

    with patch.object(settings, "messaging_enabled", True):
        with patch.object(rabbit_provider, "connect", AsyncMock()):
            await rabbit_provider.subscribe("test_queue", AsyncMock())

    assert "test_queue" in rabbit_provider._queues


@pytest.mark.asyncio
async def test_connect_already_connected(rabbit_provider):
    mock_connection = AsyncMock()
    mock_connection.is_closed = False
    rabbit_provider._connection = mock_connection
    with patch("aio_pika.connect_robust", AsyncMock()) as mock_connect:
        with patch.object(settings, "messaging_enabled", True):
            await rabbit_provider.connect()
            mock_connect.assert_not_called()


@pytest.mark.asyncio
async def test_connect_failure(rabbit_provider):
    with patch("aio_pika.connect_robust", AsyncMock(side_effect=Exception("Connection error"))) as mock_connect:
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            with patch.object(settings, "messaging_enabled", True):
                with pytest.raises(Exception, match="Connection error"):
                    await rabbit_provider.connect()
                assert mock_connect.call_count == 3
                assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_subscribe_reconnects(rabbit_provider):
    rabbit_provider._channel = None
    mock_channel = AsyncMock()
    mock_queue = MagicMock()
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
    mock_queue.iterator.return_value.__aenter__ = AsyncMock()
    with patch.object(settings, "messaging_enabled", True):
        with patch.object(rabbit_provider, "connect", AsyncMock()) as mock_connect:

            async def mock_connect_impl():
                rabbit_provider._channel = mock_channel

            mock_connect.side_effect = mock_connect_impl
            await rabbit_provider.subscribe("test_queue", AsyncMock())
            mock_connect.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_error_no_channel(rabbit_provider):
    rabbit_provider._channel = None
    with patch.object(settings, "messaging_enabled", True):
        with patch.object(rabbit_provider, "connect", AsyncMock()):
            with pytest.raises(RuntimeError, match="RabbitMQ channel not initialized"):
                await rabbit_provider.subscribe("test_queue", AsyncMock())


@pytest.mark.asyncio
async def test_subscribe_message_processing(rabbit_provider):
    mock_channel = AsyncMock()
    mock_queue = MagicMock()
    rabbit_provider._channel = mock_channel
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

    mock_iter_ctx = MagicMock()
    mock_iter_ctx.__aenter__ = AsyncMock()
    mock_iter_ctx.__aexit__ = AsyncMock()
    mock_queue.iterator = MagicMock(return_value=mock_iter_ctx)

    class AsyncList:
        def __init__(self, items):
            self.items = items

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self.items:
                raise StopAsyncIteration
            return self.items.pop(0)

    mock_msg1 = MagicMock()
    mock_msg1.body = b'{"data": "valid"}'
    mock_msg1.process.return_value.__aenter__ = AsyncMock()
    mock_msg1.process.return_value.__aexit__ = AsyncMock()

    mock_msg2 = MagicMock()
    mock_msg2.body = b"invalid-json"
    mock_msg2.process.return_value.__aenter__ = AsyncMock()
    mock_msg2.process.return_value.__aexit__ = AsyncMock()

    mock_iter_ctx.__aenter__.return_value = AsyncList([mock_msg1, mock_msg2])

    callback = AsyncMock()

    with patch.object(settings, "messaging_enabled", True):
        await rabbit_provider.subscribe("test_queue", callback)

    callback.assert_called_once_with({"data": "valid"})
