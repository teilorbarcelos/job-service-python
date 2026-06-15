import pytest
from unittest.mock import AsyncMock, patch
from src.modules.audit.audit_events import handle_audit_event
from src.infra.messaging.rabbitmq_provider import consumer


@pytest.mark.asyncio
async def test_handle_audit_event_with_valid_message():
    with patch("src.modules.audit.audit_events.audit_service.save_audit", AsyncMock()) as mock_save:
        await handle_audit_event({"type": "audit", "id_user": "123", "key": "val"})
        mock_save.assert_called_once_with({"id_user": "123", "key": "val"})


@pytest.mark.asyncio
async def test_handle_audit_event_ignores_non_audit():
    with patch("src.modules.audit.audit_events.audit_service.save_audit", AsyncMock()) as mock_save:
        await handle_audit_event({"type": "other", "key": "val"})
        mock_save.assert_not_called()


def test_consumer_decorator_registers():
    _consumers_before = len(__import__("src.infra.messaging.rabbitmq_provider", fromlist=["_consumers"])._consumers)

    @consumer(queue="test_queue", exchange="test_ex", exchange_type="topic")
    async def dummy_handler(msg): ...

    from src.infra.messaging.rabbitmq_provider import _consumers

    assert "test_queue" in _consumers
    assert _consumers["test_queue"]["exchange"] == "test_ex"
    assert _consumers["test_queue"]["exchange_type"] == "topic"
