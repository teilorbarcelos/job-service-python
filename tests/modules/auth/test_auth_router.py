import pytest
import uuid
import bcrypt
from httpx import AsyncClient
from src.infra.database.models import User, Role, Auth
from unittest.mock import patch
from src.shared.config import messages


@pytest.mark.asyncio
class TestAuthEndpoints:
    async def test_should_authenticate_a_user_with_valid_credentials(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        user_id = f"u_{uid}"
        auth_id = f"a_{uid}"

        hashed = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        session.add(Role(id=role_id, name="Admin", description="D"))
        session.add(Auth(id=auth_id, password=hashed, active=True))
        session.add(User(id=user_id, name="Test User", email=f"{uid}@test.com", id_role=role_id, id_auth=auth_id))
        await session.commit()

        response = await client.post("/v1/auth/login", json={"email": f"{uid}@test.com", "password": "password123"})

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == f"{uid}@test.com"

    async def test_should_return_401_if_password_is_wrong(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        hashed = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        session.add(Role(id=f"r_{uid}", name="Admin", description="D"))
        session.add(Auth(id=f"a_{uid}", password=hashed, active=True))
        session.add(User(id=f"u_{uid}", name="Test User", email=f"{uid}@test.com", id_role=f"r_{uid}", id_auth=f"a_{uid}"))
        await session.commit()

        response = await client.post("/v1/auth/login", json={"email": f"{uid}@test.com", "password": "wrong"})
        assert response.status_code == 401

    async def test_should_return_401_if_account_is_disabled(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        hashed = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        session.add(Role(id=f"r_{uid}", name="Admin", description="D"))
        session.add(Auth(id=f"a_{uid}", password=hashed, active=False))
        session.add(User(id=f"u_{uid}", name="Test User", email=f"{uid}@test.com", id_role=f"r_{uid}", id_auth=f"a_{uid}"))
        await session.commit()

        response = await client.post("/v1/auth/login", json={"email": f"{uid}@test.com", "password": "password123"})
        assert response.status_code == 401
        assert response.json()["message"] == "Account is disabled"

    async def test_should_return_401_if_account_is_locked(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        hashed = bcrypt.hashpw("password123".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        session.add(Role(id=f"r_{uid}", name="Admin", description="D"))
        session.add(Auth(id=f"a_{uid}", password=hashed, active=True, retries=5))
        session.add(User(id=f"u_{uid}", name="Test User", email=f"{uid}@test.com", id_role=f"r_{uid}", id_auth=f"a_{uid}"))
        await session.commit()

        response = await client.post("/v1/auth/login", json={"email": f"{uid}@test.com", "password": "password123"})
        assert response.status_code == 401
        assert response.json()["message"] == "Account locked due to excessive failed attempts"

    async def test_auth_router_me_missing_header_bypass_auth(self, client: AsyncClient, admin_user_override):
        response = await client.get("/v1/auth/me")
        assert response.status_code == 401

    async def test_me_without_authorization_header(self, client: AsyncClient):
        response = await client.get("/v1/auth/me")
        assert response.status_code == 401
        assert response.json()["message"] == "Invalid or expired token"

    async def test_refresh_endpoint(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        mock_response = {
            "message": "ok",
            "valid": True,
            "token": "t",
            "refreshToken": "rt",
            "user": {"id": "1", "name": "N", "email": "e@e.com", "role": {"id": "r", "name": "R", "description": "D", "permissions": []}},
        }
        with patch.object(auth_service, "refresh", return_value=mock_response) as mock_refresh:
            response = await client.post("/v1/auth/refresh", json={"refreshToken": "token"})
            assert response.status_code == 200
            mock_refresh.assert_called_once_with("token")

    async def test_password_request_endpoint(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        with patch.object(auth_service, "request_password_reset", return_value={"message": "ok"}) as mock_req:
            response = await client.post("/v1/auth/password/request", json={"email": "test@test.com"})
            assert response.status_code == 200
            mock_req.assert_called_once_with("test@test.com")

    async def test_password_validate_endpoint(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        with patch.object(auth_service, "validate_password_reset_token", return_value={"valid": True}) as mock_val:
            response = await client.post("/v1/auth/password/validate", json={"email": "test@test.com", "token": "123"})
            assert response.status_code == 200
            mock_val.assert_called_once_with("test@test.com", "123")

    async def test_password_change_endpoint(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        with patch.object(auth_service, "change_password", return_value={"message": "ok"}) as mock_change:
            response = await client.post("/v1/auth/password/change", json={"email": "test@test.com", "token": "123", "password": "new"})
            assert response.status_code == 200
            mock_change.assert_called_once_with("test@test.com", "123", "new")

    async def test_should_logout_endpoint(self, client: AsyncClient):
        response = await client.post("/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == messages.LOGGED_OUT_SUCCESSFULLY

    async def test_should_logout_with_token(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        with patch.object(auth_service, "logout", return_value={"message": messages.LOGGED_OUT_SUCCESSFULLY}) as mock_logout:
            response = await client.post("/v1/auth/logout", headers={"Authorization": "Bearer test-token"})
            assert response.status_code == 200
            mock_logout.assert_called_once_with("test-token")

    async def test_should_logout_all_endpoint(self, client: AsyncClient):
        response = await client.post("/v1/auth/logout-all")
        assert response.status_code == 200
        assert response.json()["message"] == messages.LOGGED_OUT_SUCCESSFULLY

    async def test_should_logout_all_with_token(self, client: AsyncClient):
        from src.modules.auth.auth_service import auth_service

        with patch.object(auth_service, "logout_all", return_value={"message": messages.ALL_SESSIONS_REVOKED}) as mock_logout_all:
            response = await client.post("/v1/auth/logout-all", headers={"Authorization": "Bearer test-token"})
            assert response.status_code == 200
            mock_logout_all.assert_called_once_with("test-token")

    async def test_should_return_user_info_for_valid_token(self, client: AsyncClient, admin_user_override):
        from src.modules.auth.auth_service import auth_service

        mock_user_info = {
            "message": "Login successful",
            "valid": True,
            "token": "valid-token",
            "refreshToken": "valid-refresh-token",
            "user": {
                "id": "admin-id",
                "name": "Admin",
                "email": "admin@email.com",
                "role": {"id": "administrator", "name": "Administrator", "description": "D", "permissions": []},
            },
        }

        with patch.object(auth_service, "get_me", return_value=mock_user_info) as mock_get_me:
            response = await client.get("/v1/auth/me", headers={"Authorization": "Bearer valid-token"})
            assert response.status_code == 200
            assert response.json()["user"]["email"] == "admin@email.com"
            mock_get_me.assert_called_once_with("valid-token")
