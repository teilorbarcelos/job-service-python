import pytest
import uuid
from httpx import AsyncClient
from src.infra.database.models import User, Role
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
class TestUserEndpoints:
    @pytest.fixture(autouse=True)
    def setup_auth_override(self, admin_user_override):
        pass

    async def test_should_list_users_with_pagination(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        role = Role(id=role_id, name="Operator", description="D")
        session.add(role)
        session.add(User(id=f"u1_{uid}", name="U1", email=f"u1_{uid}@test.com", id_role=role_id))
        session.add(User(id=f"u2_{uid}", name="U2", email=f"u2_{uid}@test.com", id_role=role_id))
        await session.commit()

        response = await client.get("/v1/user?page=0&size=10", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2

    async def test_should_create_a_new_user(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        role = Role(id=role_id, name="Operator", description="D")
        session.add(role)
        await session.commit()

        payload = {"name": "New User", "email": f"new_{uid}@test.com", "id_role": role_id}
        response = await client.post("/v1/user", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 201
        assert response.json()["name"] == "New User"

    async def test_should_return_404_if_user_not_found(self, client: AsyncClient):
        response = await client.get("/v1/user/non-existent", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

    async def test_should_return_user_by_id(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        user_id = f"u_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=user_id, name="Test User", email=f"{uid}@test.com", id_role=role_id))
        await session.commit()

        response = await client.get(f"/v1/user/{user_id}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["id"] == user_id

    async def test_should_update_a_user(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        user_id = f"u_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=user_id, name="Old Name", email=f"{uid}@test.com", id_role=role_id))
        await session.commit()

        response = await client.put(f"/v1/user/{user_id}", json={"name": "New Name"}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    async def test_should_delete_a_user(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        user_id = f"u_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=user_id, name="Test", email=f"{uid}@test.com", id_role=role_id))
        await session.commit()

        response = await client.delete(f"/v1/user/{user_id}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 204

    async def test_should_toggle_user_status(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        user_id = f"u_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=user_id, name="Test", email=f"{uid}@test.com", id_role=role_id, active=True))
        await session.commit()

        response = await client.patch(f"/v1/user/{user_id}/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200

        from sqlalchemy import select

        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user_db = res.scalar()
        assert user_db.active is False

    async def test_should_list_all_users_alias(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=f"u_alias_{uid}", name="Alias User", email=f"alias_{uid}@test.com", id_role=role_id))
        await session.commit()

        response = await client.get("/v1/user/all", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_should_filter_users_by_name_and_active(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        session.add(Role(id=role_id, name="Operator", description="D"))
        session.add(User(id=f"u_f1_{uid}", name="Target", email=f"f1_{uid}@test.com", id_role=role_id, active=True))
        session.add(User(id=f"u_f2_{uid}", name="Other", email=f"f2_{uid}@test.com", id_role=role_id, active=False))
        await session.commit()

        response = await client.get("/v1/user?name=Target&active=true", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Target"

    async def test_should_return_404_on_missing_user_actions(self, client: AsyncClient):

        response = await client.delete("/v1/user/missing_u", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

        response = await client.patch("/v1/user/missing_u/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

    async def test_user_router_direct_coverage(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from src.modules.user.router import get_user_by_id, delete_user, toggle_status

        with patch("src.modules.user.router.user_service") as mock_svc:
            mock_svc.repo.find_one_by_id = AsyncMock(return_value={"id": "1", "name": "U1"})
            res = await get_user_by_id("1", {})
            assert res == {"id": "1", "name": "U1"}

            mock_svc.delete = AsyncMock(return_value=True)
            res = await delete_user("1", {})
            assert res is None

            mock_svc.set_status = AsyncMock(return_value={"id": "1", "active": True})
            res = await toggle_status("1", MagicMock(active=True), {})
            assert res["active"] is True

            from fastapi import HTTPException

            mock_svc.delete = AsyncMock(return_value=False)
            with pytest.raises(HTTPException):
                await delete_user("missing", {})

            mock_svc.set_status = AsyncMock(return_value=None)
            with pytest.raises(HTTPException):
                await toggle_status("missing", MagicMock(active=True), {})

    async def test_export_users_pdf_success(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        role = Role(id=role_id, name="Operator", description="D")
        session.add(role)
        session.add(User(id=f"u1_{uid}", name="User PDF One", email=f"pdf1_{uid}@test.com", id_role=role_id, active=True))
        session.add(User(id=f"u2_{uid}", name="User PDF Two", email=f"pdf2_{uid}@test.com", id_role=role_id, active=True))
        await session.commit()

        async def mock_generate_pdf(request_dto):
            assert request_dto.template == "user-list"
            assert "users" in request_dto.data
            assert any(u["name"] == "User PDF One" for u in request_dto.data["users"])
            assert any(u["name"] == "User PDF Two" for u in request_dto.data["users"])
            yield b"%PDF-1.4 mock pdf content"

        with patch("src.infra.pdf.pdf_provider.pdf_provider.generate_pdf", side_effect=mock_generate_pdf):
            response = await client.get(
                "/v1/user/export/pdf?name=User&orderBy=name&orderDirection=asc", headers={"Authorization": "Bearer token"}
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert 'attachment; filename="usuarios.pdf"' in response.headers["content-disposition"]
            assert response.content == b"%PDF-1.4 mock pdf content"

    async def test_export_users_pdf_fallback(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        role = Role(id=role_id, name="Operator", description="D")
        session.add(role)
        session.add(User(id=f"u1_{uid}", name="User PDF One", email=f"pdf1_{uid}@test.com", id_role=role_id, active=True))
        await session.commit()

        with patch("httpx.AsyncClient.stream", side_effect=Exception("Service Down")):
            response = await client.get("/v1/user/export/pdf", headers={"Authorization": "Bearer token"})
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            assert response.content.startswith(b"%PDF")
            assert b"Mock PDF Content" in response.content

    async def test_get_user_by_id_not_found_extra(self, client: AsyncClient):
        response = await client.get("/v1/user/non-existent-user-id", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    async def test_export_pdf_direct(self, session):
        uid = str(uuid.uuid4())[:8]
        role_id = f"role_{uid}"
        role = Role(id=role_id, name="Operator", description="D")
        session.add(role)
        session.add(User(id=f"u1_{uid}", name="User PDF One", email=f"pdf1_{uid}@test.com", id_role=role_id, active=True))
        await session.commit()

        from src.modules.user.user_service import user_service

        async def mock_generate_pdf(request_dto):
            yield b"%PDF-1.4 mock pdf content"

        with patch("src.infra.pdf.pdf_provider.pdf_provider.generate_pdf", side_effect=mock_generate_pdf):
            generator = await user_service.export_pdf({"name": "User"})
            chunks = []
            async for chunk in generator:
                chunks.append(chunk)
            assert len(chunks) == 1
            assert chunks[0] == b"%PDF-1.4 mock pdf content"

    async def test_export_users_pdf_router_direct(self):
        from src.modules.user.router import export_users_pdf
        from unittest.mock import MagicMock

        async def mock_export_pdf(query):
            async def dummy_gen():
                yield b"dummy"

            return dummy_gen()

        with patch("src.modules.user.router.user_service.export_pdf", side_effect=mock_export_pdf):
            request = MagicMock()
            request.query_params = {"name": "User"}
            response = await export_users_pdf(request)
            assert response is not None

            body = []
            async for chunk in response.body_iterator:
                body.append(chunk)
            assert b"".join(body) == b"dummy"
