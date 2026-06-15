import json
from contextvars import ContextVar
from datetime import datetime
from decimal import Decimal
from typing import Any


class AuditJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def audit_json_dumps(data: Any) -> str:
    return json.dumps(data, cls=AuditJSONEncoder)


audit_context: ContextVar[dict[str, Any]] = ContextVar("audit_context", default=None)


def set_audit_data(table_name: str | None = None, diff_value: str | None = None, error: str | None = None):
    current = audit_context.get()
    if current is not None:
        if table_name:
            current["table_name"] = table_name
        if diff_value:
            current["diff_value"] = diff_value
        if error:
            current["error"] = error


def get_audit_data() -> dict[str, Any]:
    return audit_context.get() or {}


def init_audit_context():
    audit_context.set({})
