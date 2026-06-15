import pytest
import json
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
from src.infra.redis.redis_provider import redis_provider


@pytest.mark.asyncio
class TestIdempotencyMiddleware:
    async def test_should_bypass_get_requests(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_should_bypass_without_idempotency_key(self, client: AsyncClient):
        response = await client.post("/v1/auth/login", json={"email": "t@t.com", "password": "p"})
        assert response.status_code != 409

    async def test_should_return_409_on_different_body(self, client: AsyncClient):
        key = "test-idem-001"
        cached = json.dumps(
            {
                "body_hash": "different_hash",
                "status": 200,
                "response_body": {"message": "cached"},
                "headers": {},
            }
        )
        with patch.object(redis_provider, "get", new_callable=AsyncMock, return_value=cached):
            response = await client.post(
                "/v1/auth/login",
                json={"email": "t@t.com", "password": "p"},
                headers={"Idempotency-Key": key},
            )
            assert response.status_code == 409
            assert "Conflict" in response.text

    async def test_should_return_cached_response(self, client: AsyncClient):
        import hashlib

        key = "test-idem-002"
        body_bytes = b'{"email": "t@t.com", "password": "p"}'
        expected_hash = hashlib.sha256(body_bytes).hexdigest()[:16]
        cached = json.dumps(
            {
                "body_hash": expected_hash,
                "status": 200,
                "response_body": {"message": "from cache"},
                "headers": {},
            }
        )
        with patch.object(redis_provider, "get", new_callable=AsyncMock, return_value=cached):
            response = await client.post(
                "/v1/auth/login",
                content=body_bytes,
                headers={"Idempotency-Key": key, "Content-Type": "application/json"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("message") == "from cache"

    async def test_should_cache_new_response(self, client: AsyncClient):
        key = "test-idem-003"
        with patch.object(redis_provider, "get", new_callable=AsyncMock, return_value=None):
            with patch.object(redis_provider, "setex", new_callable=AsyncMock) as mock_setex:
                response = await client.post(
                    "/v1/auth/login",
                    json={"email": "invalid@test.com", "password": "wrong"},
                    headers={"Idempotency-Key": key},
                )
                assert mock_setex.called
                assert response.headers.get("X-Idempotency-Key") == key

    async def test_should_handle_invalid_cached_data_gracefully(self, client: AsyncClient):
        key = "test-idem-004"
        with patch.object(redis_provider, "get", new_callable=AsyncMock, return_value="invalid-json"):
            with patch.object(redis_provider, "setex", new_callable=AsyncMock):
                response = await client.post(
                    "/v1/auth/login",
                    json={"email": "t@t.com", "password": "wrong"},
                    headers={"Idempotency-Key": key},
                )
                assert response.status_code in [401, 422]
