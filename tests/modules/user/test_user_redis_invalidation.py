import pytest
from src.modules.user.user_service import UserService
from src.infra.database.models import User, Role, Auth
from src.shared.config.settings import settings
from unittest.mock import AsyncMock


@pytest.fixture
def service():
    return UserService()


@pytest.mark.asyncio
class TestUserRedisInvalidation:
    async def test_should_invalidate_redis_session_on_update(self, service, session, mocker):
        mock_redis = mocker.patch("src.modules.user.user_service.redis_provider", new_callable=AsyncMock)

        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="user_id", email="test@test.com", name="Original", id_role="operator")
        session.add(user)
        await session.commit()

        await service.update("user_id", {"name": "New Name"})

        mock_redis.invalidate_sessions.assert_called_once_with("user_id")

    async def test_should_invalidate_redis_session_on_delete(self, service, session, mocker):
        mock_redis = mocker.patch("src.modules.user.user_service.redis_provider", new_callable=AsyncMock)

        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="del_id", email="del@test.com", name="D", id_role="operator")
        session.add(user)
        await session.commit()

        await service.delete("del_id")

        mock_redis.invalidate_sessions.assert_called_once_with("del_id")

    async def test_should_invalidate_redis_session_on_status_change(self, service, session, mocker):
        mock_redis = mocker.patch("src.modules.user.user_service.redis_provider", new_callable=AsyncMock)

        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="stat_id", email="stat@test.com", name="S", id_role="operator", active=True)
        session.add(user)
        await session.commit()

        await service.set_status("stat_id", False)

        mock_redis.invalidate_sessions.assert_called_once_with("stat_id")
