"""Async health checker for the job runner.

Default implementation that pings the actual PG/Redis/RabbitMQ
providers. Tests inject a custom HealthChecker via the constructor.
"""

from __future__ import annotations

import logging

from src.infra.database import db as database
from src.infra.messaging import rabbitmq_provider
from src.infra.redis import redis_provider
from src.jobs.health_check_job import HealthCheckerProtocol, HealthCheckResult

logger = logging.getLogger("health")

__all__ = ["DefaultHealthChecker", "HealthCheckerProtocol"]


class DefaultHealthChecker:
    """Production health checker that talks to the real providers."""

    async def check_postgres(self) -> HealthCheckResult:
        import asyncio

        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            pool = await database.get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return HealthCheckResult(status="up", latency_ms=int((loop.time() - start) * 1000))
        except Exception as exc:
            logger.error("[HealthCheck] PostgreSQL failed: %s", exc)
            return HealthCheckResult(
                status="down", latency_ms=int((loop.time() - start) * 1000), error=str(exc)
            )

    async def check_redis(self) -> HealthCheckResult:
        import asyncio

        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            client = redis_provider.get_client()
            pong = await client.ping()
            if pong is True or pong == "PONG":
                return HealthCheckResult(status="up", latency_ms=int((loop.time() - start) * 1000))
            return HealthCheckResult(
                status="down", latency_ms=int((loop.time() - start) * 1000), error="unexpected reply"
            )
        except Exception as exc:
            logger.error("[HealthCheck] Redis failed: %s", exc)
            return HealthCheckResult(
                status="down", latency_ms=int((loop.time() - start) * 1000), error=str(exc)
            )

    async def check_rabbitmq(self) -> HealthCheckResult:
        from src.shared.config.settings import settings

        if not settings.messaging_enabled:
            return HealthCheckResult(status="disabled")
        try:
            if rabbitmq_provider.messaging_provider.check():
                return HealthCheckResult(status="up")
            return HealthCheckResult(status="down", error="connection closed")
        except Exception as exc:
            logger.error("[HealthCheck] RabbitMQ failed: %s", exc)
            return HealthCheckResult(status="down", error=str(exc))
