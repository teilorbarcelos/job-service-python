import pytest
from src.shared.middlewares.auth_middleware import check_auth
from src.infra.auth.auth_provider import auth_provider
from fastapi import HTTPException


@pytest.mark.asyncio
class TestAuthMiddleware:
    async def test_should_raise_401_if_token_not_provided(self, mocker):
        mock_req = mocker.Mock()
        with pytest.raises(HTTPException) as exc:
            await check_auth(mock_req, None)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid or expired token"

    async def test_should_raise_401_if_token_invalid(self, mocker):
        mock_req = mocker.Mock()
        mocker.patch.object(auth_provider, "verify_token", return_value=None)
        with pytest.raises(HTTPException) as exc:
            await check_auth(mock_req, "Bearer invalid")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid or expired token"

    async def test_should_return_payload_if_token_valid(self, mocker):
        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com", "roleId": "admin"}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)

        result = await check_auth(mock_req, "Bearer valid-token")
        assert result == payload
        assert mock_req.state.user == payload

    async def test_should_handle_token_with_extra_quotes(self, mocker):
        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com"}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)

        result = await check_auth(mock_req, 'Bearer "quoted-token"')
        assert result == payload

    async def test_should_raise_401_if_session_revoked(self, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from unittest.mock import AsyncMock

        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com", "roleId": "admin"}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=False)

        with pytest.raises(HTTPException) as exc:
            await check_auth(mock_req, "Bearer valid-token")
        assert exc.value.status_code == 401
        assert "revoked" in exc.value.detail.lower() or "invalid" in exc.value.detail.lower()

    async def test_should_accept_token_with_ver_mismatch_but_no_cache(self, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from unittest.mock import AsyncMock

        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com", "roleId": "admin", "ver": 1}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=True)

        result = await check_auth(mock_req, "Bearer valid-token")
        assert result == payload
        assert mock_req.state.user == payload

    async def test_should_reject_token_when_ver_mismatch(self, mocker):
        from unittest.mock import AsyncMock

        from src.infra.redis.redis_provider import redis_provider

        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com", "roleId": "admin", "ver": 1}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)
        redis_provider.is_session_valid = AsyncMock(return_value=True)
        redis_provider.get_session_version = AsyncMock(return_value=2)

        with pytest.raises(HTTPException) as exc:
            await check_auth(mock_req, "Bearer valid-token")
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    async def test_should_handle_ver_check_exception_gracefully(self, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from unittest.mock import AsyncMock

        mock_req = mocker.Mock()
        payload = {"id": "user123", "email": "test@test.com", "roleId": "admin", "ver": 1}
        mocker.patch.object(auth_provider, "verify_token", return_value=payload)
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=True)
        mocker.patch.object(redis_provider, "get_session_version", new_callable=AsyncMock, side_effect=Exception("Redis down"))

        result = await check_auth(mock_req, "Bearer valid-token")
        assert result == payload
