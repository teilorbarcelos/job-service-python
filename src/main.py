import asyncio
import glob
import os
import sys

IS_TEST = "pytest" in sys.modules or "test" in "".join(sys.argv)


def _remove_stale_db_file(filepath: str):
    filename = os.path.basename(filepath)
    try:
        parts = filename.rstrip(".db").split("_")
        if len(parts) >= 2:
            pid = int(parts[-1])
            try:
                os.kill(pid, 0)
            except OSError:
                os.remove(filepath)
    except Exception:
        pass


def _cleanup_stale_multiproc_files():
    if IS_TEST:
        return
    if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = "/tmp/prometheus_multiproc"
    multiproc_dir = os.environ["PROMETHEUS_MULTIPROC_DIR"]
    try:
        if not os.path.exists(multiproc_dir):
            os.makedirs(multiproc_dir, exist_ok=True)
        else:
            for filepath in glob.glob(os.path.join(multiproc_dir, "*.db")):
                _remove_stale_db_file(filepath)
    except Exception:
        try:
            os.makedirs(multiproc_dir, exist_ok=True)
        except Exception:
            pass


from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from src.infra.database.db import close_engine, get_engine
from src.shared.middlewares.audit_middleware import audit_middleware
from src.shared.middlewares.error_handlers import global_exception_handler, http_exception_handler, validation_exception_handler
from src.shared.middlewares.idempotency_middleware import idempotency_middleware
from src.shared.utils.logging import get_logger

logger = get_logger("main")
from contextlib import asynccontextmanager

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest, multiprocess

from src.infra.database.db import IS_TEST
from src.infra.messaging.rabbitmq_provider import rabbitmq_provider
from src.modules.auth.router import router as auth_router
from src.modules.dashboard.router import router as dashboard_router
from src.modules.feature.router import router as feature_router
from src.modules.health.router import router as health_router
from src.modules.product.router import router as product_router
from src.modules.role.router import router as role_router
from src.modules.user.router import router as user_router
from src.shared.config.settings import settings
from src.shared.middlewares.logging_middleware import logging_middleware
from src.shared.middlewares.rate_limit_middleware import rate_limit_middleware
from src.shared.utils.bootstrap import bootstrap_system


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not IS_TEST:
        _cleanup_stale_multiproc_files()
        get_engine()
        await bootstrap_system()
        try:
            await rabbitmq_provider.connect()
            if settings.messaging_enabled:
                await rabbitmq_provider.setup_topology()
                await rabbitmq_provider.start_consumers()
        except Exception as e:
            logger.warning(f"RabbitMQ initial connection failed: {e}")

        from src.infra.outbox.outbox_service import outbox_service

        asyncio.create_task(outbox_service.worker_loop())

        try:
            from src.infra.metrics.metric_service import metric_service

            metric_service._get_or_create_counter("http_requests_total", ["method", "status", "path"])
            metric_service._get_or_create_histogram("http_request_duration_ms", ["method", "path"])
            metric_service._get_or_create_counter("db_queries_total", []).inc(0)

            exc_counter = metric_service._get_or_create_counter("exceptions_total", ["status", "type"])
            exc_counter.labels(type="ValidationError", status="422").inc(0)
            exc_counter.labels(type="HTTPException", status="401").inc(0)
            exc_counter.labels(type="HTTPException", status="403").inc(0)
            exc_counter.labels(type="HTTPException", status="404").inc(0)
            exc_counter.labels(type="HTTPException", status="429").inc(0)
            exc_counter.labels(type="Exception", status="500").inc(0)
            metric_service.start_process_metrics_tracker()
        except Exception as e:
            logger.warning(f"Metrics initialization failed: {e}")

    yield

    if not IS_TEST:
        try:
            await rabbitmq_provider.disconnect()
        except Exception:
            pass
        try:
            await close_engine()
        except Exception:
            pass
        from src.infra.redis.redis_provider import redis_provider

        try:
            await redis_provider.client.aclose()
        except Exception:
            pass


app = FastAPI(title="Backend Python", lifespan=lifespan, docs_url="/v1/docs", openapi_url="/v1/swagger.json")

allowed_origins = settings.cors_allowed_origins.split(",") if settings.cors_allowed_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if settings.cors_allowed_origins != "*" else False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key"],
)

if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in settings.cors_allowed_origins.split(",") if h.strip()],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


@app.middleware("http")
async def idempotency(request: Request, call_next):
    return await idempotency_middleware(request, call_next)


@app.middleware("http")
async def audit(request: Request, call_next):
    return await audit_middleware(request, call_next)


@app.middleware("http")
async def logging(request: Request, call_next):
    return await logging_middleware(request, call_next)


if settings.auth_mode != "remote":
    app.include_router(auth_router)
app.include_router(user_router)
app.include_router(role_router)
app.include_router(feature_router)
app.include_router(product_router)
app.include_router(health_router)
app.include_router(dashboard_router)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/health")
async def health_check_alias(response: Response):
    from src.modules.health.router import health_check

    return await health_check(response)


@app.get("/liveness")
async def liveness_check():
    return {"status": "ok"}


import logging


class MetricsLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/metrics" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(MetricsLogFilter())


@app.get("/metrics")
async def metrics():
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if multiproc_dir and os.path.isdir(multiproc_dir) and os.listdir(multiproc_dir):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        data = generate_latest(registry)
    else:
        data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
