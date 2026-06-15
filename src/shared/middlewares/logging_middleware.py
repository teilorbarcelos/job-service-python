import json
import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request

from src.infra.metrics.metric_service import metric_service
from src.shared.config.settings import settings

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")
_trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")


def get_request_id() -> str:
    return _request_id_ctx.get()


def get_user_id() -> str:
    return _user_id_ctx.get()


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id_ctx.get(),
            "user_id": _user_id_ctx.get(),
        }
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if record.args:
            log_entry["args"] = str(record.args)
        return json.dumps(log_entry, default=str)


logger = logging.getLogger("api")
log_level_val = getattr(logging, settings.log_level.upper(), logging.INFO)
logger.setLevel(log_level_val)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)


def structured_log(level: str, message: str, **kwargs):
    log_record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper(), logging.INFO),
        "",
        0,
        message,
        (),
        None,
    )
    log_record.extra_fields = kwargs
    logger.handle(log_record)


async def logging_middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]
    _request_id_ctx.set(request_id)
    request.state.request_id = request_id

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000
    method = request.method
    path = request.url.path
    status = response.status_code
    ip = request.client.host if request.client else "unknown"

    user_info = getattr(request.state, "user", {})
    user_id = user_info.get("id") if isinstance(user_info, dict) else ""
    if user_id:
        _user_id_ctx.set(user_id)

    structured_log(
        "info",
        "request_processed",
        method=method,
        path=path,
        status=status,
        duration_ms=round(duration_ms, 2),
        ip=ip,
    )

    metric_service.increment_counter(
        "http_requests_total",
        method=method,
        status=str(status),
        path=path,
    )

    metric_service.record_timer(
        "http_request_duration_ms",
        duration_ms,
        method=method,
        path=path,
    )

    response.headers["X-Request-ID"] = request_id

    return response
