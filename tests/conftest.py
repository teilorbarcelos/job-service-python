import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("MESSAGING_ENABLED", "false")

from unittest.mock import AsyncMock

import sys


class MockRedisModule:
    redis_provider = AsyncMock()


MockRedisModule.redis_provider.client = AsyncMock()
MockRedisModule.redis_provider.is_locked = AsyncMock(return_value=False)
MockRedisModule.redis_provider.is_session_valid = AsyncMock(return_value=True)
MockRedisModule.redis_provider.get_session_version = AsyncMock(return_value=None)
MockRedisModule.redis_provider.remove_token_from_session = AsyncMock()
MockRedisModule.redis_provider.set_session = AsyncMock()
MockRedisModule.redis_provider.set_permissions = AsyncMock()
MockRedisModule.redis_provider.get_permissions = AsyncMock(return_value=None)
MockRedisModule.redis_provider.invalidate_permissions = AsyncMock()
MockRedisModule.redis_provider.set_session_version = AsyncMock()
MockRedisModule.redis_provider.invalidate_session_version = AsyncMock()
MockRedisModule.redis_provider.invalidate_sessions = AsyncMock()
MockRedisModule.redis_provider.increment_lockout = AsyncMock()
MockRedisModule.redis_provider.reset_lockout = AsyncMock()


sys.modules["src.infra.redis.redis_provider"] = MockRedisModule

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.infra.database.base import Base
from src.infra.database.db import get_engine, get_async_session_factory, set_test_session
from src.infra.messaging.rabbitmq_provider import rabbitmq_provider
from src.main import app
from src.shared.middlewares.auth_middleware import check_auth

import src.infra.database.models


@pytest.fixture
def admin_user_override():
    app.dependency_overrides[check_auth] = lambda: {"id": "admin-id", "email": "admin@email.com", "roleId": "administrator"}
    yield
    app.dependency_overrides.clear()


rabbitmq_provider._connection = AsyncMock()
rabbitmq_provider._connection.is_closed = False
rabbitmq_provider._channel = AsyncMock()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    if os.path.exists("test.db"):
        try:
            os.remove("test.db")
        except Exception:
            pass

    _engine = get_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await _engine.dispose()
    if os.path.exists("test.db"):
        try:
            os.remove("test.db")
        except Exception:
            pass


@pytest_asyncio.fixture
async def session(setup_db):
    _factory = get_async_session_factory()
    async with _factory() as _session:
        set_test_session(_session)
        yield _session
        set_test_session(None)


@pytest_asyncio.fixture
async def client(setup_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
