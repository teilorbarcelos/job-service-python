import pytest
import bcrypt
import datetime
from sqlalchemy import select
from fastapi import HTTPException
from unittest.mock import patch, MagicMock, AsyncMock
from src.modules.auth.auth_service import AuthService, auth_service
from src.shared.config import messages
from src.infra.database.models import User, Role, Auth, Feature, RoleFeature
from src.infra.auth.auth_provider import auth_provider
from src.infra.redis.redis_provider import redis_provider


@pytest.fixture
def service():
    return AuthService()


@pytest.mark.asyncio
class TestAuthService:
    async def test_should_login_successfully(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        hashed = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        auth = Auth(id="a1", password=hashed, active=True)
        user = User(id="u1", email="login@test.com", name="N", id_role="admin", id_auth="a1", active=True)
        session.add_all([auth, user])
        await session.commit()

        result = await service.login("login@test.com", "pass123")
        assert "token" in result
        assert result["user"]["email"] == "login@test.com"

    async def test_should_fail_login_with_wrong_password(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        hashed = bcrypt.hashpw("correct".encode(), bcrypt.gensalt()).decode()
        auth = Auth(id="a1", password=hashed, active=True, retries=0)
        user = User(id="u1", email="fail@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.login("fail@test.com", "wrong")
        assert exc.value.status_code == 401

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a1"))).scalar_one()
        assert updated_auth.retries == 1

    async def test_should_fail_login_if_user_inactive(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=False)
        user = User(id="u1", email="inactive@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.login("inactive@test.com", "p")
        assert "disabled" in exc.value.detail

    async def test_should_fail_if_account_locked(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="any", active=True, retries=5)
        user = User(id="u1", email="locked@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.login("locked@test.com", "any")
        assert exc.value.status_code == 401
        assert "locked" in exc.value.detail

    async def test_should_get_me_successfully(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=True)
        user = User(id="u1", email="me@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        token = auth_provider.generate_token({"id": "u1", "email": "me@test.com"})
        result = await service.get_me(token)
        assert result["user"]["email"] == "me@test.com"

    async def test_should_fail_get_me_without_token(self, service):
        with pytest.raises(HTTPException) as exc:
            await service.get_me(None)
        assert exc.value.status_code == 401

    async def test_should_request_and_validate_password_reset(self, service, session, mocker):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="any", active=True)
        user = User(id="u1", email="reset@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        mocker.patch("secrets.token_urlsafe", return_value="known-plaintext-token")
        await service.request_password_reset("reset@test.com")

        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a1"))).scalar_one()
        stored_hash = updated_auth.request_password_token
        assert stored_hash is not None
        assert bcrypt.checkpw(b"known-plaintext-token", stored_hash.encode())

        val = await service.validate_password_reset_token("reset@test.com", "known-plaintext-token")
        assert val["valid"] is True

    async def test_should_fail_if_reset_token_invalid_or_expired(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        exp = datetime.datetime.now() - datetime.timedelta(hours=1)
        token_hash = bcrypt.hashpw("123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        auth = Auth(id="a1", password="p", request_password_token=token_hash, request_password_expiration=exp)
        user = User(id="u1", email="expired@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.validate_password_reset_token("expired@test.com", "123")
        assert "expired" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            await service.validate_password_reset_token("expired@test.com", "wrong")
        assert "Invalid" in exc.value.detail

    async def test_should_fail_if_user_disabled_during_get_me(self, service, session, mocker):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=False)
        user = User(id="u1", email="disabled@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        token = auth_provider.generate_token({"id": "u1", "email": "disabled@test.com"})
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=True)

        with pytest.raises(HTTPException) as exc:
            await service.get_me(token)
        assert exc.value.status_code == 401

    async def test_should_fail_login_if_user_profile_inactive(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        hashed = bcrypt.hashpw("p".encode(), bcrypt.gensalt()).decode()
        auth = Auth(id="a1", password=hashed, active=True)
        user = User(id="u1", email="user-inactive@test.com", name="N", id_role="admin", id_auth="a1", active=False)
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.login("user-inactive@test.com", "p")
        assert exc.value.status_code == 401
        assert "disabled" in exc.value.detail

    async def test_should_fail_get_me_if_user_profile_inactive(self, service, session, mocker):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=True)
        user = User(id="u1", email="user-me-inactive@test.com", name="N", id_role="admin", id_auth="a1", active=False)
        session.add_all([auth, user])
        await session.commit()

        token = auth_provider.generate_token({"id": "u1", "email": "user-me-inactive@test.com"})
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=True)

        with pytest.raises(HTTPException) as exc:
            await service.get_me(token)
        assert exc.value.status_code == 401
        assert "disabled" in exc.value.detail

    async def test_should_change_password_with_token(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        exp = datetime.datetime.now() + datetime.timedelta(hours=1)
        token_hash = bcrypt.hashpw("123456".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        auth = Auth(id="a1", password="old", active=True, request_password_token=token_hash, request_password_expiration=exp)
        user = User(id="u1", email="change@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        await service.change_password("change@test.com", "123456", "new_secret")
        updated_auth = (await session.execute(select(Auth).where(Auth.id == "a1"))).scalar_one()
        assert bcrypt.checkpw("new_secret".encode(), updated_auth.password.encode())

    async def test_should_refresh_token_successfully(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=True)
        user = User(id="u1", email="refresh@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        refresh_token = auth_provider.generate_token({"id": "u1", "email": "refresh@test.com"})
        result = await service.refresh(refresh_token)
        assert "token" in result

    async def test_should_fail_refresh_if_user_disabled(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=False)
        user = User(id="u1", email="ref-disabled@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        refresh_token = auth_provider.generate_token({"id": "u1", "email": "ref-disabled@test.com"})
        with pytest.raises(HTTPException) as exc:
            await service.refresh(refresh_token)
        assert "disabled" in exc.value.detail

    async def test_login_user_role_disabled(self, session):
        role_id = "role_disabled"
        auth_id = "auth_disabled"
        hashed = bcrypt.hashpw("pass123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        session.add(Role(id=role_id, name="Disabled", description="D", active=False))
        session.add(Auth(id=auth_id, password=hashed, active=True))
        session.add(User(id="u_disabled", name="U", email="disabled@test.com", id_role=role_id, id_auth=auth_id))
        await session.commit()
        with pytest.raises(HTTPException) as exc:
            await auth_service.login("disabled@test.com", "pass123")
        assert exc.value.status_code == 401

    async def test_get_me_session_revoked(self, session):
        token = auth_provider.generate_token({"id": "u_me", "email": "me@test.com"})
        redis_provider.is_session_valid.return_value = False
        with patch.object(
            auth_service.repo, "find_first_with_user", AsyncMock(return_value={"user": {"active": True, "role": {"active": True}}})
        ):
            with pytest.raises(HTTPException) as exc:
                await auth_service.get_me(token)
            assert exc.value.status_code == 401
            assert "revoked" in exc.value.detail.lower() or "invalid" in exc.value.detail.lower()
        redis_provider.is_session_valid.return_value = True

    async def test_refresh_invalid_session_mock(self, service, session, mocker):
        token = auth_provider.generate_token({"id": "u1", "email": "refresh-invalid@test.com"})
        mocker.patch.object(redis_provider, "is_session_valid", new_callable=AsyncMock, return_value=False)
        with patch.object(
            auth_service.repo,
            "find_first_with_user",
            AsyncMock(return_value={"active": True, "user": {"id": "u", "email": "e@e.com", "active": True}}),
        ):
            with pytest.raises(HTTPException) as exc:
                await auth_service.refresh(token)
            assert exc.value.status_code == 401

    async def test_auth_service_errors_coverage(self, service, session, mocker):

        with patch.object(service.repo, "find_first_with_user", AsyncMock(return_value={})):
            with pytest.raises(HTTPException) as exc:
                await service.login("none@test.com", "p")
            assert exc.value.status_code == 401

        with patch("src.infra.auth.auth_provider.auth_provider.verify_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await service.get_me("invalid")
            assert exc.value.status_code == 401

        with patch("src.infra.auth.auth_provider.auth_provider.verify_token", return_value={"id": "u", "email": "e@e.com"}):
            with patch.object(redis_provider, "is_session_valid", AsyncMock(return_value=True)):
                with patch.object(service.repo, "find_first_with_user", AsyncMock(return_value={"user": {"role": {"active": False}}})):
                    with pytest.raises(HTTPException) as exc:
                        await service.get_me("token")
                    assert "role is disabled" in exc.value.detail

        with patch("src.infra.auth.auth_provider.auth_provider.verify_token", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await service.refresh("token")
            assert exc.value.status_code == 401

        with patch.object(service.repo, "find_first_with_user", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                await service.request_password_reset("none@test.com")
            assert exc.value.status_code == 404

        with patch.object(service.repo, "find_first_with_user", AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                await service.validate_password_reset_token("none@test.com", "token")
            assert exc.value.status_code == 404

        with patch.object(service.repo, "find_first_with_user", AsyncMock(return_value={"id": "a", "email": "e@e.com"})):
            with patch.object(service.repo, "update_record_details", AsyncMock()):
                from src.infra.email.email_provider import email_provider

                with patch.object(email_provider, "send_email", side_effect=Exception("Email error")):
                    res = await service.request_password_reset("e@e.com")
                    assert res["message"] == "Recovery email sent successfully"

    async def test_should_logout_successfully(self, service, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from src.infra.auth.auth_provider import auth_provider
        from unittest.mock import AsyncMock

        mocker.patch.object(auth_provider, "verify_token", return_value={"id": "user1"})
        mock_remove = mocker.patch.object(redis_provider, "remove_token_from_session", new_callable=AsyncMock)
        result = await service.logout("some-token")
        assert result["message"] == messages.LOGGED_OUT_SUCCESSFULLY
        mock_remove.assert_called_once_with("user1", "some-token")

    async def test_should_logout_all_successfully(self, service, session, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from src.infra.auth.auth_provider import auth_provider
        from unittest.mock import AsyncMock

        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a1", password="p", active=True)
        user = User(id="u1", email="logout-all@test.com", name="N", id_role="admin", id_auth="a1")
        session.add_all([auth, user])
        await session.commit()

        token = auth_provider.generate_token({"id": "u1", "email": "logout-all@test.com"})
        mocker.patch.object(redis_provider, "invalidate_session_version", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_sessions", new_callable=AsyncMock)
        mocker.patch.object(redis_provider, "invalidate_permissions", new_callable=AsyncMock)
        mocker.patch.object(service.repo, "find_first_with_user", return_value={"id": "a1", "user": {"id": "u1"}})

        result = await service.logout_all(token)
        assert result["message"] == messages.ALL_SESSIONS_REVOKED

    async def test_should_handle_logout_with_invalid_token(self, service, mocker):
        from src.infra.auth.auth_provider import auth_provider

        mocker.patch.object(auth_provider, "verify_token", return_value=None)
        result = await service.logout("invalid-token")
        assert result["message"] == messages.LOGGED_OUT_SUCCESSFULLY

    async def test_should_handle_logout_all_with_invalid_token(self, service, mocker):
        from src.infra.auth.auth_provider import auth_provider

        mocker.patch.object(auth_provider, "verify_token", return_value=None)
        result = await service.logout_all("invalid-token")
        assert result["message"] == messages.ALL_SESSIONS_REVOKED

    async def test_validate_password_reset_handles_malformed_token(self, service, session):
        session.add(Role(id="admin", name="Admin", description="D", active=True))
        auth = Auth(id="a_mal", password="p", active=True, request_password_token="not-a-valid-bcrypt-hash")
        user = User(id="u_mal", email="malformed@test.com", name="N", id_role="admin", id_auth="a_mal")
        session.add_all([auth, user])
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await service.validate_password_reset_token("malformed@test.com", "token")
        assert exc.value.status_code == 401

    async def test_build_session_sets_permissions_cache(self, service, session):
        from src.infra.redis.redis_provider import redis_provider
        from unittest.mock import AsyncMock

        session.add(Role(id="admin", name="Admin", description="D", active=True))
        feat = Feature(id="feat1", name="Feat", description="D")
        session.add(feat)
        hashed = bcrypt.hashpw("pass".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        auth = Auth(id="a_perms", password=hashed, active=True)
        user = User(id="u_perms", email="perms@test.com", name="N", id_role="admin", id_auth="a_perms")
        session.add_all([auth, user])
        session.add(RoleFeature(id_role="admin", id_feature="feat1", create=True, view=True, delete=False, activate=False))
        await session.commit()

        redis_provider.set_permissions = AsyncMock()
        result = await service.login("perms@test.com", "pass")
        assert "token" in result

    async def test_auth_service_lockout_error_branches(self, service, mocker):
        from src.infra.redis.redis_provider import redis_provider
        from unittest.mock import AsyncMock

        mocker.patch.object(redis_provider, "is_locked", new_callable=AsyncMock, return_value=True)
        with pytest.raises(HTTPException) as exc:
            await service.login("locked@test.com", "any")
        assert exc.value.status_code == 401
        assert "locked" in exc.value.detail

        mocker.patch.object(redis_provider, "is_locked", new_callable=AsyncMock, side_effect=Exception("Redis error"))
        mocker.patch.object(service.repo, "find_first_with_user", return_value=None)
        with pytest.raises(HTTPException) as exc:
            await service.login("error@test.com", "any")
        assert exc.value.status_code == 401

    async def test_refresh_with_role_features(self, session):
        uid = "ref_rf"
        role_id = f"r_{uid}"
        auth_id = f"a_{uid}"
        feat_id = f"f_{uid}"
        session.add(Role(id=role_id, name="Role", description="D", active=True))
        session.add(Feature(id=feat_id, name="Feat", description="D", active=True))
        session.add(Auth(id=auth_id, active=True))
        session.add(User(id=f"u_{uid}", name="U", email=f"{uid}@test.com", id_role=role_id, id_auth=auth_id))
        session.add(RoleFeature(id_role=role_id, id_feature=feat_id, create=True, view=True, delete=False, activate=False))
        await session.commit()
        rt = auth_provider.generate_token_pair({"id": f"u_{uid}", "email": f"{uid}@test.com"})["refreshToken"]
        with patch.object(redis_provider, "is_session_valid", AsyncMock(return_value=True)):
            res = await auth_service.refresh(rt)
            assert len(res["user"]["role"]["permissions"]) == 1
