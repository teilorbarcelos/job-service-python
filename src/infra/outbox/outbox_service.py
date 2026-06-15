import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select, update

from src.infra.database.db import get_session
from src.infra.messaging.rabbitmq_provider import rabbitmq_provider
from src.infra.outbox.models import Outbox
from src.shared.config.settings import settings

logger = logging.getLogger(__name__)


class OutboxService:
    def __init__(self):
        self._wake_event = asyncio.Event()

    async def publish(
        self,
        event_type: str,
        payload: dict,
        aggregate_type: str = "",
        aggregate_id: str | None = None,
        routing_key: str | None = None,
        exchange: str | None = None,
    ):
        outbox_id = None
        async with get_session() as session:
            outbox = Outbox(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=json.dumps(payload),
                routing_key=routing_key,
                exchange=exchange,
            )
            session.add(outbox)
            await session.flush()
            outbox_id = outbox.id

            if not settings.messaging_enabled:
                await self._process_directly(event_type, payload)
                await session.execute(
                    update(Outbox)
                    .where(Outbox.id == outbox_id)
                    .values(processed=True, processed_at=datetime.now())
                )
            else:
                self._wake_event.set()

            await session.commit()

    async def process_pending(self, batch_size: int = 50) -> int:
        async with get_session() as session:
            result = await session.execute(
                select(Outbox)
                .where(Outbox.processed == False)
                .order_by(Outbox.created_at)
                .limit(batch_size)
            )
            pending = result.scalars().all()

        if not pending:
            return 0

        processed_ids: list[str] = []
        for record in pending:
            try:
                payload = json.loads(record.payload)

                if settings.messaging_enabled:
                    await rabbitmq_provider.publish(
                        queue_name=record.routing_key or record.event_type,
                        message=payload,
                        exchange=record.exchange,
                        routing_key=record.routing_key,
                    )
                else:
                    await self._process_directly(record.event_type, payload)

                processed_ids.append(record.id)
            except Exception as e:
                logger.warning(f"[Outbox] Failed to publish {record.id}: {e}")

        if processed_ids:
            async with get_session() as session:
                await session.execute(
                    update(Outbox)
                    .where(Outbox.id.in_(processed_ids))
                    .values(processed=True, processed_at=datetime.now())
                )
                await session.commit()

        return len(processed_ids)

    async def _process_directly(self, event_type: str, payload: dict):
        if event_type.startswith("audit.") and payload.get("type") == "audit":
            from src.modules.audit.audit_service import audit_service

            audit_data = {k: v for k, v in payload.items() if k != "type"}
            await audit_service.save_audit(audit_data)

    async def worker_loop(self, idle_interval: float = 60.0):
        if not settings.messaging_enabled:
            logger.info("[Outbox] Worker disabled (MESSAGING_ENABLED=false)")
            return

        consecutive_failures = 0
        while True:
            try:
                self._wake_event.clear()
                count = await self.process_pending()

                if count > 0:
                    consecutive_failures = 0
                    continue

                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"[Outbox] Worker error (#{consecutive_failures}): {e}")

            wait = min(idle_interval * (2 ** consecutive_failures), 300.0) if consecutive_failures else idle_interval
            try:
                await asyncio.wait_for(self._wake_event.wait(), timeout=wait)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass


outbox_service = OutboxService()
