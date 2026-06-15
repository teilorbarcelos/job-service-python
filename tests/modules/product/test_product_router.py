import pytest
import uuid
from httpx import AsyncClient
from src.infra.database.models import Product, Role
from src.infra.auth.auth_provider import auth_provider


@pytest.mark.asyncio
class TestProductEndpoints:
    @pytest.fixture(autouse=True)
    def setup_auth_override(self, admin_user_override):
        pass

    async def test_should_create_a_product(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        payload = {
            "name": f"Product {uid}",
            "sku": f"SKU_{uid}",
            "category": "Electronics",
            "price": 100.50,
            "stock": 10,
            "description": "Test product",
        }
        response = await client.post("/v1/product", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 201
        res_data = response.json()
        assert res_data["name"] == f"Product {uid}"
        assert res_data["id_user"] == "admin-id"

    async def test_should_list_products_with_pagination(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Product(id=f"p1_{uid}", name="P1", sku=f"S1_{uid}", category="C", price=10, stock=1, description="D"))
        session.add(Product(id=f"p2_{uid}", name="P2", sku=f"S2_{uid}", category="C", price=20, stock=1, description="D"))
        await session.commit()

        response = await client.get("/v1/product?page=0&size=10", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2

    async def test_should_list_all_products(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        session.add(Product(id=f"pall_{uid}", name="PAll", sku=f"SALL_{uid}", category="C", price=10, stock=1, description="D"))
        await session.commit()
        response = await client.get("/v1/product/all", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert any(i["id"] == f"pall_{uid}" for i in response.json()["items"])

    async def test_should_get_product_by_id(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        p = Product(id=f"get_{uid}", name="Get Me", sku=f"SKU_GET_{uid}", category="C", price=10, stock=1, description="D")
        session.add(p)
        await session.commit()

        response = await client.get(f"/v1/product/get_{uid}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "Get Me"

    async def test_should_update_product(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        p = Product(id=f"upd_{uid}", name="Old", sku=f"SKU_UPD_{uid}", category="C", price=10, stock=1, description="D")
        session.add(p)
        await session.commit()

        payload = {"name": "Updated Product", "price": 150.00}
        response = await client.put(f"/v1/product/upd_{uid}", json=payload, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Product"

    async def test_should_delete_product(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        p = Product(id=f"del_{uid}", name="Del", sku=f"SKU_DEL_{uid}", category="C", price=10, stock=1, description="D")
        session.add(p)
        await session.commit()

        response = await client.delete(f"/v1/product/del_{uid}", headers={"Authorization": "Bearer token"})
        assert response.status_code == 204

    async def test_should_toggle_product_status(self, client: AsyncClient, session):
        uid = str(uuid.uuid4())[:8]
        p = Product(id=f"tog_{uid}", name="Tog", sku=f"SKU_TOG_{uid}", category="C", price=10, stock=1, description="D", active=True)
        session.add(p)
        await session.commit()

        response = await client.patch(f"/v1/product/tog_{uid}/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json()["active"] is False

    async def test_should_return_404_on_missing_id(self, client: AsyncClient):
        response = await client.get("/v1/product/missing_p", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

        response = await client.delete("/v1/product/missing_p", headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

        response = await client.patch("/v1/product/missing_p/status", json={"active": False}, headers={"Authorization": "Bearer token"})
        assert response.status_code == 404

    async def test_product_router_direct_coverage(self):
        from unittest.mock import patch, MagicMock, AsyncMock
        from src.modules.product.router import get_product, delete_product, toggle_status

        with patch("src.modules.product.router.product_service") as mock_svc:
            mock_svc.repo.find_one_by_id = AsyncMock(return_value={"id": "1", "name": "P1"})
            res = await get_product("1", {})
            assert res == {"id": "1", "name": "P1"}

            mock_svc.delete = AsyncMock(return_value=True)
            res = await delete_product("1", {})
            assert res is None

            mock_svc.set_status = AsyncMock(return_value={"id": "1", "active": True})
            res = await toggle_status("1", MagicMock(active=True), {})
            assert res["active"] is True
