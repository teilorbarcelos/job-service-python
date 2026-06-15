import pytest
import uuid
from datetime import datetime, timedelta
from httpx import AsyncClient
from src.infra.database.models import User, Product
from src.shared.middlewares.auth_middleware import check_auth
from src.main import app


@pytest.mark.asyncio
class TestDashboardEndpoints:
    @pytest.fixture(autouse=True)
    def setup_auth_override(self):

        app.dependency_overrides[check_auth] = lambda: {
            "id": "admin-id",
            "email": "admin@email.com",
            "roleId": "administrator",
            "permissions": [{"feature": "dashboard", "create": True, "view": True, "delete": True, "activate": True}],
        }
        yield
        app.dependency_overrides.clear()

    async def test_should_get_empty_dashboard_stats(self, client: AsyncClient, session):
        response = await client.get("/v1/dashboard/stats", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()
        assert "userCreationStats" in data
        assert "productCreationStats" in data
        assert "productsPerUser" in data
        assert len(data["userCreationStats"]) == 0
        assert len(data["productCreationStats"]) == 0
        assert len(data["productsPerUser"]) == 0

    async def test_should_deny_access_to_non_admin_without_permission(self, client: AsyncClient):

        app.dependency_overrides[check_auth] = lambda: {
            "id": "operator-id",
            "email": "operator@email.com",
            "roleId": "operator",
            "permissions": [],
        }
        response = await client.get("/v1/dashboard/stats", headers={"Authorization": "Bearer token"})
        assert response.status_code == 403

    async def test_should_return_correct_aggregations_and_date_filtering(self, client: AsyncClient, session):

        u1_id = f"u1_{str(uuid.uuid4())[:8]}"
        u2_id = f"u2_{str(uuid.uuid4())[:8]}"
        u3_id = f"u3_{str(uuid.uuid4())[:8]}"

        today = datetime.now()
        five_days_ago = today - timedelta(days=5)
        forty_days_ago = today - timedelta(days=40)

        session.add(User(id=u1_id, name="User One", email="u1@test.com", id_role="operator", created_at=today))
        session.add(User(id=u2_id, name="User Two", email="u2@test.com", id_role="operator", created_at=five_days_ago))
        session.add(User(id=u3_id, name="User Three", email="u3@test.com", id_role="operator", created_at=forty_days_ago))

        p1 = Product(
            id=f"p1_{u1_id}",
            name="Prod 1",
            sku="SKU_1",
            category="Cat A",
            price=10.0,
            stock=5,
            description="D",
            id_user=u1_id,
            created_at=today,
        )
        p2 = Product(
            id=f"p2_{u1_id}",
            name="Prod 2",
            sku="SKU_2",
            category="Cat A",
            price=20.0,
            stock=5,
            description="D",
            id_user=u1_id,
            created_at=five_days_ago,
        )
        p3 = Product(
            id=f"p3_{u1_id}",
            name="Prod 3",
            sku="SKU_3",
            category="Cat B",
            price=30.0,
            stock=5,
            description="D",
            id_user=u2_id,
            created_at=five_days_ago,
        )
        p4 = Product(
            id=f"p4_{u1_id}",
            name="Prod 4",
            sku="SKU_4",
            category="Cat B",
            price=40.0,
            stock=5,
            description="D",
            id_user=u2_id,
            created_at=forty_days_ago,
        )
        session.add_all([p1, p2, p3, p4])
        await session.commit()

        response = await client.get("/v1/dashboard/stats", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        data = response.json()

        assert len(data["userCreationStats"]) == 2

        dates = [item["date"] for item in data["userCreationStats"]]
        assert dates[0] == five_days_ago.strftime("%Y-%m-%d")
        assert dates[1] == today.strftime("%Y-%m-%d")
        assert data["userCreationStats"][0]["count"] == 1
        assert data["userCreationStats"][1]["count"] == 1

        assert len(data["productCreationStats"]) == 2
        p_dates = [item["date"] for item in data["productCreationStats"]]
        assert p_dates[0] == five_days_ago.strftime("%Y-%m-%d")
        assert p_dates[1] == today.strftime("%Y-%m-%d")

        assert data["productCreationStats"][0]["count"] == 2

        assert data["productCreationStats"][1]["count"] == 1

        assert len(data["productsPerUser"]) == 2
        assert data["productsPerUser"][0]["userId"] == u1_id
        assert data["productsPerUser"][0]["userName"] == "User One"
        assert data["productsPerUser"][0]["count"] == 2

        assert data["productsPerUser"][1]["userId"] == u2_id
        assert data["productsPerUser"][1]["userName"] == "User Two"
        assert data["productsPerUser"][1]["count"] == 1

        start_date_str = forty_days_ago.strftime("%Y-%m-%d")
        end_date_str = today.strftime("%Y-%m-%d")
        response = await client.get(
            f"/v1/dashboard/stats?createdAt_start={start_date_str}&createdAt_end={end_date_str}", headers={"Authorization": "Bearer token"}
        )
        assert response.status_code == 200
        data_all = response.json()

        assert sum(item["count"] for item in data_all["userCreationStats"]) == 3
        assert sum(item["count"] for item in data_all["productCreationStats"]) == 4

        assert data_all["productsPerUser"][0]["count"] == 2
        assert data_all["productsPerUser"][1]["count"] == 2
