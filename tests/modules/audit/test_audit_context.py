import pytest
from src.modules.audit.audit_context import audit_json_dumps, init_audit_context, set_audit_data, get_audit_data


def test_audit_json_encoder_fallback():
    class Unserializable:
        pass

    with pytest.raises(TypeError):
        audit_json_dumps(Unserializable())


def test_audit_context_uninitialized():
    from src.modules.audit.audit_context import audit_context

    token = audit_context.set(None)
    try:
        assert get_audit_data() == {}
    finally:
        audit_context.reset(token)


def test_set_audit_data_no_context():
    from src.modules.audit.audit_context import audit_context

    token = audit_context.set(None)
    try:
        set_audit_data(table_name="test")
    finally:
        audit_context.reset(token)
