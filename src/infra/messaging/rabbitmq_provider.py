"""RabbitMQ publisher (aio-pika).

This module owns a single `aio_pika` robust connection and channel
for the whole job runner. Jobs that need to publish events use
`messaging_provider.publish(queue, message)`.

The connection is created lazily on first `connect()` call and
closed by `disconnect()` during graceful shutdown.

If `settings.messaging_enabled` is false, the provider is a no-op:
- `connect()` returns immediately without opening a connection
- `publish()` returns without sending anything
- `check()` returns false
- `disconnect()` returns without closing anything
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from src.shared.config.settings import settings

logger = logging.getLogger(__name__)


class RabbitMQProvider:
    def __init__(self) -> None:
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None

    async def connect(self) -> None:
        if not settings.messaging_enabled:
            logger.info("[RabbitMQ] Messaging disabled, skipping connect")
            return

        self._connection = await aio_pika.connect_robust(
            settings.rabbit_url, timeout=settings.rabbit_publish_timeout_s
        )
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        logger.info("[RabbitMQ] Connected")

    async def publish(self, queue: str, message: Any) -> None:
        if not settings.messaging_enabled:
            return

        if self._channel is None:
            raise RuntimeError("RabbitMQ channel not initialized")

        message_body = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._channel.default_exchange.publish(message_body, routing_key=queue)
        logger.debug("[RabbitMQ] Published to %s", queue)

    def check(self) -> bool:
        if self._connection is None:
            return False
        return not self._connection.is_closed

    async def disconnect(self) -> None:
        if self._channel is not None:
            try:
                await self._channel.close()
            except Exception as exc:
                logger.error("[RabbitMQ] Error closing channel: %s", exc)
            self._channel = None
        if self._connection is not None:
            try:
                await self._connection.close()
            except Exception as exc:
                logger.error("[RabbitMQ] Error closing connection: %s", exc)
            self._connection = None
        logger.info("[RabbitMQ] Disconnected")


messaging_provider = RabbitMQProvider()
