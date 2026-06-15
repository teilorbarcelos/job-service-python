r"""Application bootstrap.

Connects to PostgreSQL, Redis, and (optionally) RabbitMQ, registers
all jobs via \`register_jobs()\`, starts the scheduler, and installs
signal handlers for graceful shutdown.

The function is split into async phases so tests can mock each
external dependency independently.
"""

from __future__ import annotations

import logging

from src.core import Scheduler
from src.infra.database import db as database
from src.infra.messaging.rabbitmq_provider import messaging_provider
from src.infra.redis import redis_provider
from src.jobs.register_jobs import register_jobs
from src.shared.config.settings import settings
from src.shared.utils.logging import setup_logging
from src.shared.utils.shutdown import register_shutdown_handlers

logger = logging.getLogger(__name__)


async def _connect_external_services() -> None:
    """Lazy-initialize PG and Redis pools, connect RabbitMQ if enabled."""
    redis_provider.get_client()
    await database.get_pool()

    if settings.messaging_enabled:
        try:
            await messaging_provider.connect()
        except Exception as exc:
            logger.warning(
                "[Startup] Failed to connect to RabbitMQ (%s); continuing without it", exc
            )
    else:
        logger.info("[Startup] Messaging disabled (MESSAGING_ENABLED=false)")


async def cleanup() -> None:
    """Close all external connections during shutdown.

    Order matters: RabbitMQ → Redis → DB. The scheduler is stopped
    separately by the shutdown handler (see app.start()).
    """
    logger.info("[Shutdown] Closing RabbitMQ connection")
    await messaging_provider.disconnect()
    logger.info("[Shutdown] Closing Redis connection")
    await redis_provider.close()
    logger.info("[Shutdown] Closing database pool")
    await database.close_pool()


async def start() -> Scheduler:
    """Bootstrap the job runner. Returns the running Scheduler."""
    setup_logging(settings.log_level)
    logger.info(
        "Starting job-service-python (environment=%s, log_level=%s)",
        settings.environment,
        settings.log_level,
    )

    await _connect_external_services()

    scheduler = register_jobs()
    scheduler.start()
    logger.info(
        "Scheduler started with jobs: %s",
        [j.name for j in scheduler.list_jobs()],
    )

    register_shutdown_handlers(cleanup)

    return scheduler
