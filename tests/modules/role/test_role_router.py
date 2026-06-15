import pytest
from httpx import AsyncClient
from src.infra.database.models import Role


@pytest.mark.asyncio
class TestRoleEndpoints:
    @pytest.fixture(autouse=True)
    def setup_auth_override(self, admin_user_override):
        pass

    async def test_should_list_roles(self, client: AsyncClient, session):
        session.add(Role(id="1", name="Admin", description="Desc"))
        await session.commit()

        response = await client.get("/v1/role", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Admin"
        assert "total" in data

    async def test_should_list_all_roles_alias(self, client: AsyncClient, session):
        session.add(Role(id="role_alias", name="Manager", description="Desc"))
        await session.commit()

        response = await client.get("/v1/role/all", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_should_get_role_by_id(self, client: AsyncClient, session):
        session.add(Role(id="r123", name="Role 123", description="D"))
        await session.commit()

        response = await client.get("/v1/role/r123", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "Role 123"

    async def test_should_create_role(self, client: AsyncClient, session):
        payload = {"id": "new_role", "name": "New Role", "description": "New Desc"}
        response = await client.post("/v1/role", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 201
        assert response.json()["name"] == "New Role"

    async def test_should_update_role(self, client: AsyncClient, session):
        session.add(Role(id="upd", name="Old", description="D"))
        await session.commit()

        payload = {"name": "Updated Name"}
        response = await client.put("/v1/role/upd", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_should_delete_role(self, client: AsyncClient, session):
        session.add(Role(id="del", name="Delete Me", description="D"))
        await session.commit()

        response = await client.delete("/v1/role/del", headers={"Authorization": "Bearer token"})
        assert response.status_code == 204

    async def test_should_toggle_role_status(self, client: AsyncClient, session):
        session.add(Role(id="toggle", name="Toggle", description="D", active=True))
        await session.commit()

        response = await client.patch("/v1/role/toggle/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["active"] is False

        response = await client.get("/v1/role/features", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_should_return_404_on_missing_role_actions(self, client: AsyncClient):
        response = await client.delete("/v1/role/missing_r", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404
        response = await client.patch("/v1/role/missing_r/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

    async def test_role_router_direct_coverage(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from src.modules.role.router import delete_role, toggle_status

        with patch("src.modules.role.router.role_service") as mock_svc:
            mock_svc.delete = AsyncMock(return_value=True)
            res = await delete_role("1", {})
            assert res is None

            mock_svc.set_status = AsyncMock(return_value={"id": "1", "active": True})
            res = await toggle_status("1", MagicMock(active=True), {})
            assert res["active"] is True

            from fastapi import HTTPException

            mock_svc.delete = AsyncMock(return_value=False)
            with pytest.raises(HTTPException):
                await delete_role("missing", {})

            mock_svc.set_status = AsyncMock(return_value=None)
            with pytest.raises(HTTPException):
                await toggle_status("missing", MagicMock(active=True), {})
