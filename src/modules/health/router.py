import datetime
import json
import logging
import os

from fastapi import APIRouter, Response
from sqlalchemy import text

from src.infra.database.db import get_session
from src.infra.database.models import ErrorLog
from src.infra.redis.redis_provider import redis_provider
from src.shared.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/health", tags=["Health"])

START_TIME = datetime.datetime.now()


def get_uptime():
    if os.path.exists("/proc/uptime"):
        try:
            with open("/proc/uptime") as f:
                uptime_seconds = int(float(f.readline().split()[0]))
                days = uptime_seconds // 86400
                hours = (uptime_seconds % 86400) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60
                return f"{days}d {hours}h {minutes}m {seconds}s"
        except Exception:
            pass

    delta = datetime.datetime.now() - START_TIME
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


async def check_database():
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            return {"status": "OK", "message": "Connected"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


async def check_redis():
    try:
        await redis_provider.client.ping()
        return {"status": "OK", "message": "Connected"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


from src.infra.messaging.rabbitmq_provider import rabbitmq_provider


async def check_rabbitmq():
    if not settings.messaging_enabled:
        return {"status": "DISABLED", "message": "Messaging is disabled in settings"}
    try:
        if not rabbitmq_provider._connection or rabbitmq_provider._connection.is_closed:
            await rabbitmq_provider.connect()
        return {"status": "OK", "message": "Connected"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


from src.infra.storage.storage_provider import storage_provider


async def check_storage():
    try:
        test_file = ".health_check_temp"
        storage_provider.put(test_file, b"health-check")

        if not storage_provider.exists(test_file):
            raise RuntimeError("Storage write failed: file not found after put")

        storage_provider.delete(test_file)
        return {"status": "OK", "message": "Writable"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


@router.get("")
async def health_check(response: Response):
    status = "UP"
    db_check = await check_database()
    redis_check = await check_redis()
    rabbit_check = await check_rabbitmq()

    checks = {"database": db_check, "redis": redis_check, "rabbitmq": rabbit_check, "storage": await check_storage()}

    for name, check in checks.items():
        if check["status"] not in ["OK", "DISABLED"]:
            status = "DEGRADED"
            logger.warning(f"System Health Degraded: {name} is down", extra={"check": name, "details": check["message"]})

            try:
                async with get_session() as session:
                    error_log = ErrorLog(
                        id_user="SYSTEM",
                        source="DEGRADED",
                        error_message=f"System Health Degraded: {name} is down",
                        error_data=json.dumps({"check": name, "message": check["message"]}),
                    )
                    session.add(error_log)
                    await session.commit()
            except Exception:
                pass

    data = {
        "status": status,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "deploy": {"timestamp": settings.app_deploy_timestamp, "version": settings.app_version},
        "uptime": get_uptime(),
        "checks": checks,
        "message": "API is running smoothly. All systems operational.",
    }

    response.status_code = 200 if status == "UP" else 503
    return data
