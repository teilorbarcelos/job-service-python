import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from src.modules.health.router import check_database


@pytest.mark.asyncio
class TestHealthRouter:
    async def test_health_success(self, client: AsyncClient):
        response = await client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UP"
        assert data["checks"]["database"]["status"] == "OK"

    async def test_health_router_success_direct(self):
        res = await check_database()
        assert res["status"] == "OK"

    async def test_health_degraded_db_failure(self, client: AsyncClient):
        with patch("src.modules.health.router.get_session") as mock_session_ctx:
            mock_session = MagicMock()
            mock_session.execute.side_effect = Exception("DB Connection Refused")
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            response = await client.get("/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "DEGRADED"
            assert data["checks"]["database"]["status"] == "ERROR"

    async def test_health_degraded_redis_failure(self, client: AsyncClient):
        with patch("src.infra.redis.redis_provider.redis_provider.client.ping", new_callable=AsyncMock) as mock_ping:
            mock_ping.side_effect = Exception("Redis Connection Refused")

            response = await client.get("/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "DEGRADED"
            assert data["checks"]["redis"]["status"] == "ERROR"

    async def test_health_degraded_rabbitmq_failure(self, client: AsyncClient):
        from src.infra.messaging.rabbitmq_provider import rabbitmq_provider
        from src.shared.config.settings import settings

        with patch.object(settings, "messaging_enabled", True):
            with patch.object(rabbitmq_provider, "_connection", None):
                with patch.object(rabbitmq_provider, "connect", AsyncMock(side_effect=Exception("RabbitMQ Connection Refused"))):
                    response = await client.get("/v1/health")
                    assert response.status_code == 503
                    data = response.json()
                    assert data["status"] == "DEGRADED"
                    assert data["checks"]["rabbitmq"]["status"] == "ERROR"

    async def test_health_rabbitmq_reconnect_success(self, client: AsyncClient):
        from src.infra.messaging.rabbitmq_provider import rabbitmq_provider
        from src.shared.config.settings import settings

        with patch.object(settings, "messaging_enabled", True):
            with patch.object(rabbitmq_provider, "_connection", None):
                with patch.object(rabbitmq_provider, "connect", AsyncMock()) as mock_connect:
                    response = await client.get("/v1/health")
                    assert response.status_code == 200
                    mock_connect.assert_called_once()

    async def test_health_rabbitmq_disabled(self, client: AsyncClient):
        from src.shared.config.settings import settings

        with patch.object(settings, "messaging_enabled", False):
            response = await client.get("/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["checks"]["rabbitmq"]["status"] == "DISABLED"

    async def test_health_uptime_calc(self, client: AsyncClient):
        response = await client.get("/v1/health")
        assert "uptime" in response.json()

    async def test_health_degraded_storage_failure(self, client: AsyncClient):
        from src.infra.storage.storage_provider import storage_provider

        with patch.object(storage_provider, "put", side_effect=Exception("Storage Error")):
            response = await client.get("/v1/health")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "DEGRADED"
            assert data["checks"]["storage"]["status"] == "ERROR"
            assert data["checks"]["storage"]["message"] == "Storage Error"

    async def test_health_degraded_storage_write_success_but_not_found(self, client: AsyncClient):
        from src.infra.storage.storage_provider import storage_provider

        with patch.object(storage_provider, "put", return_value=None):
            with patch.object(storage_provider, "exists", return_value=False):
                response = await client.get("/v1/health")
                assert response.status_code == 503
                data = response.json()
                assert "Storage write failed" in data["checks"]["storage"]["message"]

    async def test_health_uptime_fallback(self, client: AsyncClient):
        with patch("os.path.exists", side_effect=lambda p: False if p == "/proc/uptime" else True):
            response = await client.get("/v1/health")
            assert response.status_code == 200
            assert "uptime" in response.json()

    async def test_health_uptime_exception(self, client: AsyncClient):
        import builtins

        original_open = builtins.open

        def mocked_open(file, *args, **kwargs):
            if file == "/proc/uptime":
                raise Exception("Read Error")
            return original_open(file, *args, **kwargs)

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", side_effect=mocked_open):
                response = await client.get("/v1/health")
                assert response.status_code == 200
                assert "uptime" in response.json()
