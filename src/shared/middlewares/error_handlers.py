import traceback
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.infra.metrics.metric_service import metric_service
from src.modules.audit.audit_context import audit_json_dumps, set_audit_data
from src.modules.audit.audit_service import audit_service
from src.shared.config.settings import settings


def _is_production() -> bool:
    return settings.environment == "production"


def _problem_detail(status: int, title: str, detail: Any = None, type_: str = None) -> dict:
    if isinstance(detail, str):
        detail_str = detail
    elif detail is not None:
        detail_str = str(detail)
    else:
        detail_str = title
    return {
        "type": type_ or f"https://httpstatuses.io/{status}",
        "title": title,
        "status": status,
        "detail": detail_str,
        "message": title,
    }


async def _log_error(request: Request, exc: Exception, status_code: int, error_type: str, detail: Any, stack: str | None = None):
    try:
        metric_service.increment_counter("exceptions_total", type=error_type, status=str(status_code))

        user_info = getattr(request.state, "user", {})
        user_id = user_info.get("id") if isinstance(user_info, dict) else None

        if user_id:
            source = f"{request.method} {request.url}"
            error_data = {"status": status_code, "type": error_type, "detail": detail, "stack": stack}
            await audit_service.save_error_log(
                {
                    "id_user": str(user_id),
                    "source": source,
                    "error_message": str(exc) or "Unknown Error",
                    "error_data": audit_json_dumps(error_data),
                }
            )
    except Exception:
        pass


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    await _log_error(request, exc, 422, "ValidationError", exc.errors())
    error_data = {"status": 422, "type": "ValidationError", "detail": exc.errors()}
    set_audit_data(error=audit_json_dumps(error_data))
    detail = exc.errors() if not _is_production() else "Validation Error"
    problem = _problem_detail(422, "Validation Error", detail)
    return JSONResponse(status_code=422, content=problem)


async def http_exception_handler(request: Request, exc: HTTPException):
    error_type = getattr(exc, "error_type", "HTTPException")
    await _log_error(request, exc, exc.status_code, error_type, exc.detail)
    error_data = {"status": exc.status_code, "type": error_type, "detail": exc.detail}
    set_audit_data(error=audit_json_dumps(error_data))
    detail = exc.detail if not _is_production() else None
    problem = _problem_detail(exc.status_code, exc.detail, detail)
    if exc.status_code == 401:
        problem["error"] = "UnauthorizedError"
    return JSONResponse(status_code=exc.status_code, content=problem)


async def global_exception_handler(request: Request, exc: Exception):
    stack = traceback.format_exc() if not _is_production() else None
    error_type = exc.__class__.__name__
    error_data = {"status": 500, "type": error_type, "detail": str(exc), "stack": stack}
    set_audit_data(error=audit_json_dumps(error_data))
    await _log_error(request, exc, 500, error_type, str(exc), stack)
    detail = str(exc) if not _is_production() else None
    problem = _problem_detail(500, "Internal Server Error", detail)
    return JSONResponse(status_code=500, content=problem)
