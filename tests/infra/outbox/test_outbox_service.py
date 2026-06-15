import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.infra.outbox.outbox_service import OutboxService


@pytest.fixture
def service():
    return OutboxService()


@pytest.mark.asyncio
async def test_publish_calls_process_directly_when_disabled(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", False):
            with patch.object(service, "_process_directly", AsyncMock()) as mock_process:
                await service.publish(event_type="t", payload={"k": "v"})
                mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_publish_sets_wake_event_when_enabled(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", True):
            await service.publish(event_type="t", payload={"k": "v"})
            assert service._wake_event.is_set()


@pytest.mark.asyncio
async def test_process_pending_returns_zero_when_empty(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_get_session.return_value.__aenter__.return_value = mock_session

        count = await service.process_pending()
        assert count == 0


@pytest.mark.asyncio
async def test_process_pending_direct_path(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        from src.infra.outbox.models import Outbox

        record = Outbox(event_type="audit.test", payload='{"type": "audit", "k": "v"}')
        record.id = "test-id"

        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [record]
        mock_session.execute.return_value = AsyncMock()
        mock_session.execute.return_value.scalars = MagicMock(return_value=mock_scalars)
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", False):
            with patch.object(service, "_process_directly", AsyncMock()) as mock_process:
                count = await service.process_pending()
                assert count == 1
                mock_process.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_with_records(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        from src.infra.outbox.models import Outbox

        record = Outbox(event_type="audit.a", payload='{"type": "audit"}')
        record.id = "id-1"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [record]

        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", False):
            with patch.object(service, "_process_directly", AsyncMock()):
                count = await service.process_pending()
                assert count == 1


@pytest.mark.asyncio
async def test_process_pending_messaging_enabled(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        from src.infra.outbox.models import Outbox

        record = Outbox(event_type="test.evt", payload='{"k": "v"}')
        record.id = "id-2"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [record]
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", True):
            with patch("src.infra.outbox.outbox_service.rabbitmq_provider.publish", AsyncMock()) as mock_pub:
                count = await service.process_pending()
                assert count == 1
                mock_pub.assert_called_once()


@pytest.mark.asyncio
async def test_process_pending_error_handling(service):
    with patch("src.infra.outbox.outbox_service.get_session") as mock_get_session:
        from src.infra.outbox.models import Outbox

        record = Outbox(event_type="audit.e", payload='{"type": "audit"}')
        record.id = "err-id"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [record]
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_session.return_value.__aenter__.return_value = mock_session

        with patch("src.infra.outbox.outbox_service.settings.messaging_enabled", False):
            with patch.object(service, "_process_directly", AsyncMock(side_effect=Exception("fail"))):
                count = await service.process_pending()
                assert count == 0


@pytest.mark.asyncio
async def test_process_directly_audit(service):
    with patch("src.modules.audit.audit_service.audit_service.save_audit", AsyncMock()) as mock_save:
        await service._process_directly("audit.test", {"type": "audit", "id_user": "123"})
        mock_save.assert_called_once_with({"id_user": "123"})


@pytest.mark.asyncio
async def test_process_directly_non_audit(service):
    with patch("src.modules.audit.audit_service.audit_service.save_audit", AsyncMock()) as mock_save:
        await service._process_directly("other.event", {"type": "other"})
        mock_save.assert_not_called()
