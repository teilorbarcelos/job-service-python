import pytest
from unittest.mock import patch

pytest.importorskip("aio_pika")


@pytest.mark.asyncio
async def test_setup_topology_declares_exchanges_and_queues():
    from src.infra.messaging.rabbitmq_provider import rabbitmq_provider

    rabbitmq_provider._connection = None
    rabbitmq_provider._channel = None
    rabbitmq_provider._exchanges = {}
    rabbitmq_provider._queues = {}
    rabbitmq_provider._consumer_tasks = []

    with patch("src.infra.messaging.rabbitmq_provider.settings.messaging_enabled", True):
        await rabbitmq_provider.connect()
        await rabbitmq_provider.setup_topology()

        assert "dlx" in rabbitmq_provider._exchanges
        assert "dlq" in rabbitmq_provider._queues
        assert "audit" in rabbitmq_provider._exchanges
        assert "audit" in rabbitmq_provider._queues

        await rabbitmq_provider.disconnect()


@pytest.mark.asyncio
async def test_declare_and_publish():
    from src.infra.messaging.rabbitmq_provider import rabbitmq_provider

    rabbitmq_provider._connection = None
    rabbitmq_provider._channel = None
    rabbitmq_provider._exchanges = {}
    rabbitmq_provider._queues = {}
    rabbitmq_provider._consumer_tasks = []

    with patch("src.infra.messaging.rabbitmq_provider.settings.messaging_enabled", True):
        await rabbitmq_provider.connect()
        await rabbitmq_provider.declare_queue("test.pub", durable=False)
        await rabbitmq_provider.publish("test.pub", {"msg": "integration"})

        import asyncio
        await asyncio.sleep(0.3)

        await rabbitmq_provider.disconnect()
        assert rabbitmq_provider._channel is None or rabbitmq_provider._channel.is_closed



