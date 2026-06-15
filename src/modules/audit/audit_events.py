import json

from src.infra.messaging.rabbitmq_provider import consumer
from src.infra.outbox.outbox_service import outbox_service
from src.modules.audit.audit_service import audit_service


async def emit_auth_event(
    event_type: str,
    user_id: str,
    user_name: str = "",
    metadata: dict = None,
    error: str = "",
):
    payload = {
        "type": "audit",
        "id_user": user_id,
        "user_name": user_name,
        "method": "SYSTEM",
        "original_url": f"event://auth/{event_type}",
        "action_type": f"AUTH_{event_type.upper()}",
        "raw": json.dumps(metadata or {}),
        "function_name": event_type,
        "class_name": "AuthService",
        "error": error,
    }
    await outbox_service.publish(
        event_type=f"audit.auth.{event_type}",
        payload=payload,
        aggregate_type="Auth",
        aggregate_id=user_id if user_id != "unknown" else None,
        routing_key="audit",
        exchange="audit",
    )


async def emit_user_event(
    event_type: str,
    user_id: str,
    user_name: str = "",
    metadata: dict = None,
    error: str = "",
):
    payload = {
        "type": "audit",
        "id_user": user_id,
        "user_name": user_name,
        "method": "SYSTEM",
        "original_url": f"event://user/{event_type}",
        "action_type": f"USER_{event_type.upper()}",
        "raw": json.dumps(metadata or {}),
        "function_name": event_type,
        "class_name": "UserService",
        "error": error,
    }
    await outbox_service.publish(
        event_type=f"audit.user.{event_type}",
        payload=payload,
        aggregate_type="User",
        aggregate_id=user_id if user_id != "unknown" else None,
        routing_key="audit",
        exchange="audit",
    )


@consumer(queue="audit", exchange="audit", exchange_type="direct")
async def handle_audit_event(message: dict):
    if message.get("type") == "audit":
        audit_data = {k: v for k, v in message.items() if k != "type"}
        await audit_service.save_audit(audit_data)
