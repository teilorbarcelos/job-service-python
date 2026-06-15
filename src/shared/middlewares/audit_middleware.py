import json
import logging

from fastapi import Request

from src.infra.outbox.outbox_service import outbox_service
from src.modules.audit.audit_context import get_audit_data, init_audit_context

logger = logging.getLogger("audit_middleware")


async def _extract_body(request: Request):
    if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
        return None
    try:
        body_bytes = await request.body()
        body_raw = body_bytes.decode("utf-8")
        try:
            data = json.loads(body_raw)
            if isinstance(data, dict):
                for key in ["password", "newPassword", "currentPassword", "token", "refreshToken"]:
                    if key in data:
                        data[key] = "******"
                body_raw = json.dumps(data)
        except Exception:
            pass
        return body_raw
    except Exception:
        return None


async def _log_audit(request: Request, response, user_id, user_name):
    if not user_id or request.url.path in ["/health", "/liveness"]:
        return
    try:
        query_params = json.dumps(dict(request.query_params)) if request.query_params else None

        route = request.scope.get("route")
        handler_name = route.name if route else None
        class_name = route.endpoint.__module__ if route else None

        extra_audit = get_audit_data()
        table_name = extra_audit.get("table_name")
        diff_value = extra_audit.get("diff_value")
        error_msg = extra_audit.get("error")

        if not error_msg and response.status_code >= 400:
            error_msg = f"[{response.status_code}]"

        audit_data = {
            "id_user": user_id,
            "user_name": user_name,
            "method": request.method,
            "original_url": str(request.url),
            "ip": request.client.host if request.client else None,
            "action_type": f"API_{request.method}",
            "host": request.headers.get("host"),
            "params": query_params,
            "raw": getattr(request.state, "audit_body_raw", None),
            "function_name": handler_name,
            "class_name": class_name,
            "table_name": table_name,
            "diff_value": diff_value,
            "error": error_msg,
        }

        await outbox_service.publish(
            event_type="audit.http.request",
            payload={"type": "audit", **audit_data},
            aggregate_type="HttpRequest",
            routing_key="audit",
            exchange="audit",
        )
    except Exception:
        logger.exception("Audit middleware unexpected error")


async def audit_middleware(request: Request, call_next):

    init_audit_context()

    body_raw = await _extract_body(request)
    request.state.audit_body_raw = body_raw

    response = await call_next(request)

    user_info = getattr(request.state, "user", {})
    user_id = user_info.get("id") if isinstance(user_info, dict) else None
    user_name = user_info.get("name") if isinstance(user_info, dict) else None

    await _log_audit(request, response, user_id, user_name)

    return response
