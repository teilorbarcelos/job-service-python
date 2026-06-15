import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, Response
from src.shared.middlewares.audit_middleware import audit_middleware


@pytest.mark.asyncio
async def test_audit_middleware_receive_direct():
    request = MagicMock()
    request.method = "POST"
    request.body = AsyncMock(return_value=b'{"test": "data"}')
    call_next = AsyncMock(return_value=Response())

    await audit_middleware(request, call_next)

    cached_body = await request.body()
    assert cached_body == b'{"test": "data"}'


@pytest.mark.asyncio
async def test_audit_middleware_direct_error_branch():
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/v1/test"
    request.query_params = {}
    request.headers = {}
    request.state.user = {"email": "err@test.com"}
    request.body = AsyncMock(return_value=b"{}")

    call_next = AsyncMock(return_value=Response(status_code=400))
    await audit_middleware(request, call_next)

    with patch("src.infra.database.db.get_session") as mock_session:
        mock_session.side_effect = Exception("Audit Crash")
        await audit_middleware(request, call_next)


@pytest.mark.asyncio
async def test_audit_middleware_unexpected_error_coverage():
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url.path = "/test"
    request.state.user = {"id": "test-id", "name": "Test User", "email": "test@example.com"}

    type(request).query_params = property(lambda x: exec('raise Exception("unexpected")'))

    async def call_next(req):
        return MagicMock(status_code=200)

    await audit_middleware(request, call_next)


@pytest.mark.asyncio
async def test_audit_middleware_status_400_coverage():
    request = MagicMock(spec=Request)
    request.method = "GET"
    mock_url = MagicMock()
    mock_url.path = "/test"
    request.url = mock_url
    request.state.user = {"id": "test-id", "name": "Test User", "email": "test@example.com"}
    request.scope = {"route": None}
    request.query_params = {}
    request.headers = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"

    async def call_next(req):
        return MagicMock(status_code=400)

    with patch("src.shared.middlewares.audit_middleware.outbox_service.publish", new_callable=AsyncMock) as mock_publish:
        await audit_middleware(request, call_next)
        assert mock_publish.called
        _, kwargs = mock_publish.call_args
        assert "error" in kwargs["payload"]
