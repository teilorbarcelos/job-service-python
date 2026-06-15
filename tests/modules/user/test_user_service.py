import pytest
from unittest.mock import AsyncMock
from src.modules.user.user_service import UserService
from src.infra.database.models import User, Role, Auth
from fastapi import HTTPException
from src.shared.config.settings import settings
from sqlalchemy import select


@pytest.fixture
def service():
    return UserService()


@pytest.mark.asyncio
class TestUserServiceIntegration:
    async def test_should_create_user_successfully(self, service, session):

        session.add(Role(id="operator", name="Op", description="D"))
        await session.commit()

        data = {"email": "integration@test.com", "name": "Int User", "password": "securepassword", "id_role": "operator"}

        result = await service.create(data)
        assert result["email"] == "integration@test.com"

        stmt = select(User).where(User.email == "integration@test.com")
        user = (await session.execute(stmt)).scalar_one_or_none()
        assert user is not None
        assert user.id_auth is not None

    async def test_should_raise_400_if_user_exists(self, service, session):

        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="u1", email="exists@test.com", name="E", id_role="operator")
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.create({"email": "exists@test.com", "name": "Any"})
        assert exc.value.status_code == 400

    async def test_should_raise_400_if_email_missing(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.create({"name": "No Email"})
        assert exc.value.status_code == 400

    async def test_should_handle_email_failure_in_user_creation(self, service, session, mocker):
        session.add(Role(id="operator", name="Op", description="D"))
        await session.commit()

        mocker.patch("src.infra.email.email_provider.email_provider.send_email", side_effect=Exception("SMTP fail"))

        data = {"email": "emailfail@user.com", "name": "N", "password": "P", "id_role": "operator"}
        result = await service.create(data)
        assert result["email"] == "emailfail@user.com"

    async def test_should_update_user_password(self, service, session):
        session.add(Role(id="operator", name="Op", description="D"))
        auth = Auth(id="a1", password="old")
        user = User(id="u1", email="upd@test.com", name="U", id_role="operator", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        await service.update("u1", {"password": "new_password", "name": "Updated Name"})

        updated_user = (await session.execute(select(User).where(User.id == "u1"))).scalar_one()
        assert updated_user.name == "Updated Name"

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a1"))).scalar_one()
        import bcrypt

        assert bcrypt.checkpw("new_password".encode(), updated_auth.password.encode())

    async def test_should_enforce_admin_protections(self, service, session):

        session.add(Role(id="administrator", name="Admin", description="D"))
        user = User(id="admin_id", email=settings.first_user, name="Admin", id_role="administrator")
        session.add(user)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.delete("admin_id")
        assert exc.value.status_code == 400

        with pytest.raises(HTTPException) as exc:
            await service.set_status("admin_id", False)
        assert exc.value.status_code == 400

    async def test_should_raise_404_on_non_existent_user(self, service, session):
        with pytest.raises(HTTPException) as exc:
            await service.update("invalid", {"name": "New"})
        assert exc.value.status_code == 404

    async def test_should_bump_session_version_on_role_change(self, service, session, mocker):
        session.add(Role(id="operator", name="Op", description="D"))
        session.add(Role(id="manager", name="Manager", description="D"))
        auth = Auth(id="a_role_change", password="old")
        user = User(id="u_role_change", email="role-change@test.com", name="U", id_role="operator", id_auth="a_role_change")
        session.add_all([auth, user])
        await session.commit()

        from src.infra.redis.redis_provider import redis_provider

        mocker.patch.object(redis_provider, "invalidate_session_version", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_permissions", new_callable=AsyncMock)

        await service.update("u_role_change", {"id_role": "manager"})

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a_role_change"))).scalar_one()
        assert updated_auth.session_version == 2

    async def test_should_bump_session_version_on_deactivation_with_auth(self, service, session, mocker):
        session.add(Role(id="operator", name="Op", description="D"))
        auth = Auth(id="a_status", password="old", session_version=1)
        user = User(id="u_status", email="status@test.com", name="S", id_role="operator", id_auth="a_status")
        session.add_all([auth, user])
        await session.commit()

        from src.infra.redis.redis_provider import redis_provider

        mocker.patch.object(redis_provider, "invalidate_session_version", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)

        await service.set_status("u_status", False)

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a_status"))).scalar_one()
        assert updated_auth.session_version == 2

    async def test_should_update_admin_user_without_changing_restricted_fields(self, service, session):

        session.add(Role(id="administrator", name="Admin", description="D"))
        user = User(id="admin_id", email=settings.first_user, name="Original", id_role="administrator")
        session.add(user)
        await session.commit()

        result = await service.update("admin_id", {"name": "New Name"})

        assert result["name"] == "Original"

    async def test_should_delete_user_successfully(self, service, session):
        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="del_me", email="del@test.com", name="D", id_role="operator")
        session.add(user)
        await session.commit()

        await service.delete("del_me")

        updated = (await session.execute(select(User).where(User.id == "del_me"))).scalar_one()
        assert updated.is_deleted is True

    async def test_should_raise_404_on_delete_non_existent(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.delete("none")
        assert exc.value.status_code == 404

    async def test_should_raise_404_on_status_non_existent(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.set_status("none", True)
        assert exc.value.status_code == 404

    async def test_should_set_status_successfully(self, service, session):
        session.add(Role(id="operator", name="Op", description="D"))
        user = User(id="stat", email="stat@test.com", name="S", id_role="operator", active=True)
        session.add(user)
        await session.commit()

        await service.set_status("stat", False)
        updated = (await session.execute(select(User).where(User.id == "stat"))).scalar_one()
        assert updated.active is False
