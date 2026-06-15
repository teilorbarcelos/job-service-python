import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Response
from src.shared.config.settings import settings
from src.infra.redis.redis_provider import redis_provider
from src.shared.middlewares.rate_limit_middleware import rate_limit_middleware
from src.infra.auth.auth_provider import auth_provider


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    def get_admin_token(self):
        return auth_provider.generate_token({"id": "admin_user_id", "email": "admin@test.com", "roleId": "administrator"})

    async def test_should_allow_request_if_under_limit(self, client: AsyncClient):
        with patch.object(redis_provider.client, "evalsha", new_callable=AsyncMock) as mock_evalsha:
            mock_evalsha.return_value = [1, 1, 99]
            response = await client.get("/v1/auth/me")
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert response.status_code != 429

    async def test_should_block_request_if_over_limit(self, client: AsyncClient):
        with patch.object(redis_provider.client, "evalsha", new_callable=AsyncMock) as mock_evalsha:
            mock_evalsha.return_value = [0, 60, 10]
            response = await client.get("/v1/auth/me")
            assert response.status_code == 429
            data = response.json()
            assert data["error"] == "Too Many Requests"
            assert response.headers["X-RateLimit-Remaining"] == "0"

    async def test_should_bypass_rate_limit_for_admin(self, client: AsyncClient):
        token = self.get_admin_token()
        response = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code != 429

    async def test_should_bypass_admin_via_role_id(self, client: AsyncClient):
        from src.shared.middlewares.auth_middleware import check_auth
        from src.main import app

        app.dependency_overrides[check_auth] = lambda: {"id": "admin", "email": "a@a.com", "roleId": "administrator"}
        try:
            response = await client.get("/v1/auth/me")
            assert response.status_code != 429
        finally:
            app.dependency_overrides.clear()

    async def test_rate_limit_middleware_x_forwarded_for(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.1.1.1, 2.2.2.2"}
        request.method = "GET"
        request.url.path = "/test"
        request.state = MagicMock()
        request.state.user = None
        call_next = AsyncMock(return_value=Response())

        with patch("src.shared.middlewares.rate_limit_middleware.redis_provider.client.evalsha", new_callable=AsyncMock) as mock_evalsha:
            mock_evalsha.return_value = [1, 1, 99]
            await rate_limit_middleware(request, call_next)
            call_next.assert_called_once()

    async def test_rate_limit_middleware_exception_path(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"
        request.method = "GET"
        request.url.path = "/test"
        request.state = MagicMock()
        request.state.user = None
        call_next = AsyncMock(return_value=Response())

        with patch("src.shared.middlewares.rate_limit_middleware.redis_provider.client.evalsha", new_callable=AsyncMock) as mock_evalsha:
            mock_evalsha.side_effect = Exception("Redis crash")
            await rate_limit_middleware(request, call_next)
            call_next.assert_called_once()

    async def test_rate_limit_middleware_bypass_paths(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_rate_limit_middleware_exceeded_metric_exception(self, client: AsyncClient):
        def mock_inc(name, **labels):
            if name == "exceptions_total":
                raise Exception("Metric Error")
            return None

        with patch("src.shared.middlewares.rate_limit_middleware.redis_provider.client.evalsha", new_callable=AsyncMock) as mock_evalsha:
            mock_evalsha.return_value = [0, 60, 10]
            with patch("src.infra.metrics.metric_service.metric_service.increment_counter", side_effect=mock_inc):
                response = await client.get("/v1/auth/me")
                assert response.status_code == 429
                assert response.json()["error"] == "Too Many Requests"

    async def test_rate_limit_middleware_script_load_fallback(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"
        request.method = "GET"
        request.url.path = "/test"
        request.state = MagicMock()
        request.state.user = None
        call_next = AsyncMock(return_value=Response())

        with patch("src.shared.middlewares.rate_limit_middleware.redis_provider.client.script_load", new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = [Exception("NOSCRIPT"), None]
            with patch(
                "src.shared.middlewares.rate_limit_middleware.redis_provider.client.evalsha", new_callable=AsyncMock
            ) as mock_evalsha:
                mock_evalsha.side_effect = [Exception("NOSCRIPT"), [1, 1, 99]]
                await rate_limit_middleware(request, call_next)
                call_next.assert_called_once()
