import pytest
import uuid
from httpx import AsyncClient
from src.infra.database.models import Feature


@pytest.mark.asyncio
class TestFeatureEndpoints:
    @pytest.fixture(autouse=True)
    def setup_auth_override(self, admin_user_override):
        pass

    async def test_should_list_features(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"f1_{uid}", name="Feature 1", description="D1"))
        session.add(Feature(id=f"f2_{uid}", name="Feature 2", description="D2"))
        await session.commit()

        response = await client.get("/v1/feature", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2

    async def test_should_list_all_features_alias(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"f_all_{uid}", name="All Feature", description="D"))
        await session.commit()

        response = await client.get("/v1/feature/all", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

    async def test_should_get_feature_by_id(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"get_{uid}", name="Get", description="D"))
        await session.commit()

        response = await client.get(f"/v1/feature/get_{uid}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "Get"

    async def test_should_create_feature(self, client: AsyncClient):
        payload = {"id": "feat_new", "name": "New Feat", "description": "Desc"}
        response = await client.post("/v1/feature", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 201

    async def test_should_update_feature(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"upd_{uid}", name="Old", description="D"))
        await session.commit()

        response = await client.put(f"/v1/feature/upd_{uid}", json={"name": "New"}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "New"

    async def test_should_delete_feature(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"del_{uid}", name="Del", description="D"))
        await session.commit()

        response = await client.delete(f"/v1/feature/del_{uid}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 204

    async def test_should_toggle_feature_status(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Feature(id=f"tog_{uid}", name="Tog", description="D", active=True))
        await session.commit()

        response = await client.patch(f"/v1/feature/tog_{uid}/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["active"] is False
