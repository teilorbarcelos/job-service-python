import pytest
from src.modules.role.role_service import role_service
from src.infra.database.models import Role, Feature, RoleFeature, User, Auth
from src.infra.database.db import get_session
from unittest.mock import AsyncMock
from sqlalchemy import select
import unittest.mock as mock


@pytest.mark.asyncio
class TestRoleService:
    async def test_should_list_features(self, session):
        session.add(Feature(id="f1", name="Feature 1", description="D"))
        await session.commit()

        features = await role_service.list_features()
        assert len(features) >= 1
        assert any(f["id"] == "f1" for f in features)

    async def test_should_create_role_with_permissions(self, session):
        session.add(Feature(id="feat1", name="Feat 1", description="D"))
        await session.commit()

        data = {
            "id": "role_with_perms",
            "name": "Role with Perms",
            "description": "Desc",
            "permissions": [{"id_feature": "feat1", "create": True, "view": True, "delete": False, "activate": False}],
        }

        role = await role_service.create(data)
        assert role["id"] == "role_with_perms"
        assert len(role["RoleFeature"]) == 1
        assert role["RoleFeature"][0]["id_feature"] == "feat1"
        assert role["RoleFeature"][0]["create"] is True

    async def test_should_create_role_without_id_slugification(self, session):
        session.add(Feature(id="feat2", name="Feat 2", description="D"))
        await session.commit()

        data = {
            "name": "My Custom Role Name!",
            "description": "Desc",
            "permissions": [{"id_feature": "feat2", "create": True, "view": True, "delete": False, "activate": False}],
        }

        role = await role_service.create(data)
        assert role["id"] == "my-custom-role-name"
        assert len(role["RoleFeature"]) == 1
        assert role["RoleFeature"][0]["id_feature"] == "feat2"

    async def test_should_update_role_permissions_and_invalidate_sessions(self, session):
        session.add(Role(id="r_upd", name="Role Upd", description="D"))
        session.add(Feature(id="f_upd", name="Feat Upd", description="D"))
        session.add(User(id="u_role", name="Test User", email="u@test.com", id_role="r_upd"))
        await session.commit()

        data = {"name": "Updated Role", "active": False, "permissions": [{"id_feature": "f_upd", "view": True}]}

        from src.infra.redis.redis_provider import redis_provider

        with mock.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock) as mock_invalidate:
            updated_role = await role_service.update("r_upd", data)
            assert updated_role["name"] == "Updated Role"
            assert len(updated_role["RoleFeature"]) == 1
            mock_invalidate.assert_called_with("u_role")

    async def test_should_get_role_not_found(self):
        role = await role_service.repo.find_one_by_id("non-existent")
        assert role is None

    async def test_should_sync_permissions_empty_list(self, session):
        session.add(Role(id="r_empty", name="Role Empty", description="D"))
        await session.commit()

        async with get_session() as s:
            await role_service._sync_permissions("r_empty", [], s)
            await s.commit()

        role = await role_service.repo.find_one_by_id("r_empty")
        assert len(role["RoleFeature"]) == 0

    async def test_should_invalidate_sessions_on_role_delete(self, session, mocker):
        session.add(Role(id="r_del", name="Role Del", description="D"))
        session.add(User(id="u_del", name="Test User", email="u_del@test.com", id_role="r_del"))
        await session.commit()

        from src.infra.redis.redis_provider import redis_provider

        mock_invalidate = mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)

        await role_service.delete("r_del")
        mock_invalidate.assert_called_with("u_del")

    async def test_should_bump_session_version_when_user_has_auth(self, session, mocker):
        session.add(Role(id="r_auth", name="Role Auth", description="D"))
        auth = Auth(id="a_role", password="p", active=True, session_version=1)
        session.add(auth)
        session.add(User(id="u_auth", name="Test", email="u_auth@test.com", id_role="r_auth", id_auth="a_role"))
        await session.commit()

        from src.infra.redis.redis_provider import redis_provider

        mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_session_version", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_permissions", new_callable=AsyncMock)

        await role_service.set_status("r_auth", False)

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a_role"))).scalar_one()
        assert updated_auth.session_version == 2

    async def test_should_invalidate_sessions_on_role_status_change(self, session, mocker):
        session.add(Role(id="r_stat", name="Role Stat", description="D"))
        session.add(User(id="u_stat", name="Test User", email="u_stat@test.com", id_role="r_stat"))
        await session.commit()

        from src.infra.redis.redis_provider import redis_provider

        mock_invalidate = mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)

        await role_service.set_status("r_stat", False)
        mock_invalidate.assert_called_with("u_stat")
