import asyncio
import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection

from src.infra.messaging.rabbitmq_provider_interface import RabbitMQProviderInterface
from src.shared.config.settings import settings

logger = logging.getLogger(__name__)

_consumers: dict[str, Callable[[Any], Awaitable[None]]] = {}


def consumer(queue: str, exchange: str = "", exchange_type: str = "direct"):
    def decorator(func: Callable[[Any], Awaitable[None]]) -> Callable[[Any], Awaitable[None]]:
        _consumers[queue] = {"handler": func, "exchange": exchange, "exchange_type": exchange_type}
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


EXCHANGE_DIRECT = "direct"
EXCHANGE_TOPIC = "topic"
EXCHANGE_FANOUT = "fanout"
EXCHANGE_HEADERS = "headers"

EXCHANGE_TYPES = {
    EXCHANGE_DIRECT: aio_pika.ExchangeType.DIRECT,
    EXCHANGE_TOPIC: aio_pika.ExchangeType.TOPIC,
    EXCHANGE_FANOUT: aio_pika.ExchangeType.FANOUT,
    EXCHANGE_HEADERS: aio_pika.ExchangeType.HEADERS,
}


class RabbitMQProvider(RabbitMQProviderInterface):
    def __init__(self):
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None
        self._exchanges: dict[str, aio_pika.RobustExchange] = {}
        self._queues: dict[str, aio_pika.RobustQueue] = {}
        self._consumer_tasks: list[asyncio.Task] = []

    async def _ensure_channel(self) -> None:
        if self._channel is None or self._channel.is_closed is True:
            await self.connect()

    async def connect(self) -> None:
        if not settings.messaging_enabled:
            return

        if self._connection and not self._connection.is_closed:
            return

        retries = 3
        delay = 1
        last_exception = None

        for i in range(retries):
            try:
                self._connection = await aio_pika.connect_robust(settings.rabbit_url, timeout=10)
                self._channel = await self._connection.channel()
                self._channel.confirm_deliveries = True
                logger.info("[RabbitMQ] Connected successfully with publisher confirms")
                return
            except Exception as e:
                last_exception = e
                logger.warning(f"[RabbitMQ] Connection attempt {i + 1} failed: {e}. Retrying in {delay}s...")
                if i < retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2

        logger.error("[RabbitMQ] All connection attempts failed after retries.")
        raise last_exception

    async def declare_exchange(self, name: str, exchange_type: str = EXCHANGE_DIRECT, durable: bool = True) -> aio_pika.RobustExchange:
        await self._ensure_channel()
        etype = EXCHANGE_TYPES.get(exchange_type, aio_pika.ExchangeType.DIRECT)
        exchange = await self._channel.declare_exchange(name, etype, durable=durable)
        self._exchanges[name] = exchange
        return exchange

    async def declare_queue(
        self,
        name: str,
        durable: bool = True,
        dlq: str | None = None,
        dlq_routing_key: str | None = None,
    ) -> aio_pika.RobustQueue:
        await self._ensure_channel()
        arguments = {}
        if dlq:
            arguments["x-dead-letter-exchange"] = dlq
            arguments["x-dead-letter-routing-key"] = dlq_routing_key or name

        queue = await self._channel.declare_queue(name, durable=durable, arguments=arguments)
        self._queues[name] = queue
        return queue

    async def bind(self, queue: str, exchange: str, routing_key: str = ""):
        await self._ensure_channel()
        q = self._queues.get(queue)
        ex = self._exchanges.get(exchange)
        if not q or not ex:
            raise RuntimeError(f"Queue '{queue}' or Exchange '{exchange}' not declared. Call declare first.")
        await q.bind(ex, routing_key=routing_key)

    async def setup_topology(self):
        if not settings.messaging_enabled:
            return

        await self._ensure_channel()

        await self.declare_exchange("dlx", EXCHANGE_DIRECT, durable=True)
        await self.declare_queue("dlq", durable=True)
        await self.bind("dlq", "dlx", "dlq")

        for queue_name, config in _consumers.items():
            ex_name = config.get("exchange") or ""
            ex_type = config.get("exchange_type") or EXCHANGE_DIRECT

            if ex_name:
                await self.declare_exchange(ex_name, ex_type, durable=True)

            await self.declare_queue(queue_name, durable=True, dlq="dlx", dlq_routing_key="dlq")

            if ex_name:
                await self.bind(queue_name, ex_name, queue_name)

        logger.info(f"[RabbitMQ] Topology declared: {len(self._exchanges)} exchanges, {len(self._queues)} queues")

    async def publish(
        self,
        queue_name: str,
        message: Any,
        exchange: str | None = None,
        routing_key: str | None = None,
    ) -> None:
        if not settings.messaging_enabled:
            return

        await self._ensure_channel()

        if not self._channel:
            raise RuntimeError("RabbitMQ channel not initialized")

        exchange_obj = self._exchanges.get(exchange) if exchange else None
        if not exchange_obj:
            exchange_obj = self._channel.default_exchange

        routing_key = routing_key or queue_name

        message_body = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )

        await exchange_obj.publish(message_body, routing_key=routing_key, mandatory=True)
        logger.debug(f"[RabbitMQ] Published to {routing_key} via {exchange_obj.name}")

    async def subscribe(self, queue_name: str, callback: Callable[[Any], Awaitable[None]]) -> None:
        if not settings.messaging_enabled:
            return

        await self._ensure_channel()
        if not self._channel:
            raise RuntimeError("RabbitMQ channel not initialized")

        queue = self._queues.get(queue_name)
        if not queue:
            queue = await self.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process(requeue=True):
                    try:
                        content = json.loads(message.body.decode())
                        await callback(content)
                    except Exception as e:
                        logger.error(f"[RabbitMQ] Error processing message from {queue_name}: {e}")

    async def start_consumers(self):
        if not settings.messaging_enabled:
            return
        for queue_name, config in _consumers.items():
            handler = config["handler"]
            task = asyncio.create_task(self._run_consumer(queue_name, handler))
            self._consumer_tasks.append(task)

    async def _run_consumer(self, queue_name: str, handler: Callable[[Any], Awaitable[None]]):
        while True:
            try:
                logger.info(f"[RabbitMQ] Starting consumer for {queue_name}")
                await self.subscribe(queue_name, handler)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[RabbitMQ] Consumer {queue_name} crashed: {e}. Restarting in 5s...")
                await asyncio.sleep(5)

    async def disconnect(self) -> None:
        for task in self._consumer_tasks:
            task.cancel()
        for task in self._consumer_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._consumer_tasks.clear()

        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        logger.info("[RabbitMQ] Disconnected")


rabbitmq_provider = RabbitMQProvider()
