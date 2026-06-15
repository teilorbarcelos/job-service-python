"""Health check job.

Logs and prints (to stdout) the connection status of PostgreSQL,
Redis, and RabbitMQ every minute. The console line is the at-a-glance
"is the job runner healthy?" check; the structured logs are for
aggregation in observability backends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC
from typing import Literal, Protocol

from src.core import BaseJob, JobContext

logger = logging.getLogger("job.health-check")


JobStatus = Literal["up", "down", "disabled"]


@dataclass
class HealthCheckResult:
    status: JobStatus
    latency_ms: int | None = None
    error: str | None = None


class HealthCheckerProtocol(Protocol):
    async def check_postgres(self, signal: object) -> HealthCheckResult: ...
    async def check_redis(self, signal: object) -> HealthCheckResult: ...
    async def check_rabbitmq(self, signal: object) -> HealthCheckResult: ...


class HealthCheckJob(BaseJob):
    name = "health-check"
    description = "Reports connection status with PostgreSQL, Redis and RabbitMQ"

    def __init__(self, checker: HealthCheckerProtocol, schedule: str = "*/1 * * * *") -> None:
        super().__init__()
        self.schedule = schedule
        self._checker = checker

    async def handle(self, context: JobContext) -> None:
        import asyncio
        from datetime import datetime

        timestamp = datetime.now(UTC).isoformat()
        pg, redis_res, rabbit = await asyncio.gather(
            self._checker.check_postgres(context.signal),
            self._checker.check_redis(context.signal),
            self._checker.check_rabbitmq(context.signal),
        )
        all_up = pg.status == "up" and redis_res.status == "up" and rabbit.status == "up"

        context.logger.info(
            "Health check completed",
            extra={
                "event": "health-check",
                "status": "healthy" if all_up else "degraded",
                "timestamp": timestamp,
                "postgres": pg,
                "redis": redis_res,
                "rabbitmq": rabbit,
            },
        )
        print(
            f"[HealthCheck {timestamp}] postgres={pg.status} redis={redis_res.status} rabbitmq={rabbit.status}",
            flush=True,
        )
