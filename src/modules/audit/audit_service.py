from src.infra.database.db import get_session
from src.modules.audit.models import Audit, ErrorLog
from src.shared.utils.logging import get_logger

logger = get_logger("audit")


class AuditService:
    async def save_audit(self, audit_data: dict):
        try:
            async with get_session() as session:
                audit = Audit(**audit_data)
                session.add(audit)
                await session.commit()
        except Exception as e:
            logger.error("Failed to save audit log", exc_info=e)

    async def save_error_log(self, error_data: dict):
        try:
            async with get_session() as session:
                error_log = ErrorLog(**error_data)
                session.add(error_log)
                await session.commit()
        except Exception as e:
            logger.error("Failed to save error log", exc_info=e)


audit_service = AuditService()
