import pytest
import pytest_asyncio
import uuid
from src.core.base_repository import BaseRepository
from src.infra.database.models import Role, User, Product, Feature, RoleFeature
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, Table, Column, String, MetaData
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.helpers.repository_helpers import (
    model_to_dict,
    apply_filters,
    apply_ordering,
    get_attribute_and_join,
    apply_includes,
    build_nested_any_has_condition,
)


class MockRepository(BaseRepository[Role]):
    def __init__(self, session_factory):
        super().__init__(model=Role, session_factory=session_factory)


@pytest_asyncio.fixture
async def repo(session):
    def factory():
        return session

    return MockRepository(factory)


@pytest.mark.asyncio
class TestBaseRepository:
    async def test_should_check_if_records_exist_by_ids(self, repo, session):
        role1 = Role(id="1", name="Role 1", description="Desc")
        role2 = Role(id="2", name="Role 2", description="Desc")
        session.add_all([role1, role2])
        await session.commit()

        result = await repo.exists_by_id(["1", "2", "3"], session=session)
        assert set(result["exists"]) == {"1", "2"}
        assert result["missing"] == ["3"]

    async def test_should_activate_a_record(self, repo, session):
        role = Role(id="1", name="Role 1", description="Desc", active=False)
        session.add(role)
        await session.commit()

        result = await repo.activate_record("1", session=session)
        assert result["active"] is True

    async def test_should_soft_delete_a_record(self, repo, session):
        role = Role(id="1", name="Role 1", description="Desc", is_deleted=False)
        session.add(role)
        await session.commit()

        result = await repo.soft_delete_record("1", session=session)
        assert result["is_deleted"] is True

    async def test_should_find_one_by_query(self, repo, session):
        role = Role(id="1", name="Target Name", description="Desc")
        session.add(role)
        await session.commit()

        result = await repo.find_one_by_query({"name": "Target Name"}, session=session)
        assert result["id"] == "1"

    async def test_should_persist_many_records(self, repo, session):
        records = [{"id": "1", "name": "R1", "description": "D1"}, {"id": "2", "name": "R2", "description": "D2"}]
        result = await repo.persist_many(records, session=session)
        assert len(result) == 2

        stmt = select(Role)
        res = await session.execute(stmt)
        assert len(res.scalars().all()) == 2

    async def test_should_search_all_records(self, repo, session):
        role = Role(id="1", name="R1", description="D1")
        session.add(role)
        await session.commit()

        result = await repo.search_all(session=session)
        assert len(result) == 1

    async def test_should_count_records(self, repo, session):
        session.add_all([Role(id="1", name="R1", description="D1"), Role(id="2", name="R2", description="D2")])
        await session.commit()

        result = await repo.count_records(session=session)
        assert result == 2

    async def test_should_search_paginated_with_filters_and_ordering(self, repo, session):
        session.add_all(
            [
                Role(id="1", name="Alpha", description="D1"),
                Role(id="2", name="Beta", description="D2"),
                Role(id="3", name="Gamma", description="D3"),
            ]
        )
        await session.commit()

        result = await repo.search_paginated(
            pageable={"page": 0, "size": 2}, ordering={"orderBy": "name", "orderDirection": "asc"}, session=session
        )
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "Alpha"
        assert result["total"] == 3

        result = await repo.search_paginated(
            pageable={"page": 0, "size": 10}, filters={"andRules": [{"key": "name", "search": "Gamma", "qt": "equals"}]}, session=session
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Gamma"

    async def test_should_handle_nested_attribute_join(self, repo, session):
        role = Role(id="r1", name="Manager", description="D1")
        session.add(role)
        await session.commit()

        user = User(id="u1", name="John", email="john@test.com", id_role="r1")
        session.add(user)
        await session.commit()

        user_repo = MockRepository(lambda: session)
        user_repo.model = User

        result = await user_repo.search_paginated(
            pageable={"page": 0, "size": 10},
            filters={"andRules": [{"key": "role.name", "search": "Manager", "qt": "equals"}]},
            session=session,
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John"

    async def test_should_handle_or_rules(self, repo, session):
        session.add_all(
            [
                Role(id="1", name="Admin", description="D1"),
                Role(id="2", name="User", description="D2"),
                Role(id="3", name="Guest", description="D3"),
            ]
        )
        await session.commit()

        result = await repo.search_paginated(
            pageable={"page": 0, "size": 10},
            filters={"orRules": [{"key": "name", "search": "Admin", "qt": "equals"}, {"key": "name", "search": "User", "qt": "equals"}]},
            session=session,
        )
        assert len(result["items"]) == 2

    async def test_should_persist_and_update_without_explicit_session(self, repo, session):
        record = await repo.persist_record({"id": "p1", "name": "Persist", "description": "D"})
        assert record["id"] == "p1"
        updated = await repo.update_record_details("p1", {"name": "Updated"})
        assert updated["name"] == "Updated"
        all_items = await repo.search_all()
        assert any(i["id"] == "p1" for i in all_items)

    async def test_should_deactivate_record(self, repo, session):
        role = Role(id="d1", name="Active", description="D", active=True)
        session.add(role)
        await session.commit()
        await repo.deactivate_record("d1", session=session)
        updated = await repo.find_one_by_id("d1", session=session)
        assert updated["active"] is False

    async def test_should_include_relations_in_find_one(self, repo, session):
        role = Role(id="r_inc", name="IncRole", description="D")
        session.add(role)
        await session.commit()
        user = User(id="u_inc", name="IncUser", email="inc@test.com", id_role="r_inc")
        session.add(user)
        await session.commit()
        user_repo = MockRepository(lambda: session)
        user_repo.model = User
        result = await user_repo.find_one_by_id("u_inc", include={"role": True}, session=session)
        assert result["role"] is not None
        assert result["role"]["name"] == "IncRole"

    async def test_should_handle_ordering_desc(self, repo, session):
        session.add_all(
            [Role(id="o1", name="B", description="D"), Role(id="o2", name="A", description="D"), Role(id="o3", name="C", description="D")]
        )
        await session.commit()
        result = await repo.search_paginated(
            pageable={"page": 0, "size": 10}, ordering={"orderBy": "name", "orderDirection": "desc"}, session=session
        )
        assert result["items"][0]["name"] == "C"

    async def test_should_apply_default_filters_when_none_provided(self, repo, session):
        session.add_all(
            [
                Role(id="active", name="A", description="D", active=True, is_deleted=False),
                Role(id="deleted", name="B", description="D", active=True, is_deleted=True),
                Role(id="inactive", name="C", description="D", active=False, is_deleted=False),
            ]
        )
        await session.commit()
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, session=session)
        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == "active"

    async def test_model_to_dict_none(self):
        assert model_to_dict(None) is None

    async def test_model_to_dict_with_none_relation(self):

        user = User(id="u_none_rel", name="No Role", email="none@test.com", id_role="r1")

        user.role = None
        user.auth = None

        d = model_to_dict(user)
        assert "role" in d
        assert d["role"] is None
        assert "auth" in d
        assert d["auth"] is None

    async def test_apply_filters_comparison_operators(self, session):
        filters = {
            "andRules": [
                {"key": "price", "search": 10.0, "qt": "gte"},
                {"key": "price", "search": 100.0, "qt": "lte"},
                {"key": "price", "search": 5.0, "qt": "gt"},
                {"key": "price", "search": 200.0, "qt": "lt"},
            ]
        }
        stmt = select(Product)
        stmt = apply_filters(Product, stmt, filters)
        session.add(Product(id="p1", name="P1", sku="S1", category="C", price=50.0, stock=10, description="D"))
        await session.commit()
        result = await session.execute(stmt)
        items = result.scalars().all()
        assert len(items) == 1

    async def test_base_repository_edge_cases(self, session):
        metadata = MetaData()
        mock_table = Table("mock", metadata, Column("id", String, primary_key=True))
        stmt = select(mock_table)
        ordered_stmt = apply_ordering(mock_table, stmt, None)
        assert "ORDER BY" not in str(ordered_stmt)

        attr, _ = get_attribute_and_join(Role, select(Role), "non_existent_field", set())
        assert attr is None

        attr, _ = get_attribute_and_join(Role, select(Role), "invalid_rel.name", set())
        assert attr is None

        included_stmt = apply_includes(Role, select(Role), {"invalid_rel": True})
        assert "SELECT" in str(included_stmt)

    async def test_should_filter_by_deep_nested_attribute(self, session):
        feature = Feature(id="f1", name="F1", description="D1")
        session.add(feature)
        role_admin = Role(id="admin2", name="Administrator 2", description="Full access")
        session.add(role_admin)
        await session.flush()
        rf = RoleFeature(id_role="admin2", id_feature="f1", view=True)
        session.add(rf)
        await session.commit()
        user1 = User(id="u1_deep", name="John Admin 2", email="john2@test.com", id_role="admin2")
        session.add(user1)
        await session.commit()
        user_repo = BaseRepository(User, lambda: session)
        filters = {"andRules": [{"key": "role.role_features.view", "search": True, "qt": "equals"}]}
        result = await user_repo.search_paginated(pageable={"page": 0, "size": 10}, filters=filters, session=session)
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John Admin 2"

    async def test_build_nested_any_has_condition_operators(self):
        cond_contains = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "contains", "f")
        assert cond_contains is not None
        cond_none = build_nested_any_has_condition(User, ["role", "role_features", "non_existent"], "equals", "f1")
        assert cond_none is None

    async def test_optimizations_and_no_duplicate_joins(self, session):
        user_repo = BaseRepository(model=User, session_factory=lambda: session)
        role = Role(id="r_opt", name="Manager", description="D")
        session.add(role)
        user = User(id="u_opt", name="John", email="j@test", id_role="r_opt")
        session.add(user)
        await session.commit()
        result = await user_repo.search_paginated(
            pageable={"page": 0, "size": 10},
            filters={"andRules": [{"key": "role.name", "search": "Manager", "qt": "equals"}]},
            ordering={"orderBy": "role.name", "orderDirection": "asc"},
            session=session,
        )
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John"

    async def test_should_persist_many_without_explicit_session(self, repo):
        records = [{"id": "m_no_sess", "name": "M_NS", "description": "D"}]
        result = await repo.persist_many(records)
        assert len(result) == 1
        assert result[0]["id"] == "m_no_sess"

    async def test_apply_filters_or_rules_equals_mock(self, session):
        filters = {"orRules": [{"key": "name", "search": "R1", "qt": "equals"}, {"key": "description", "search": "D1", "qt": "contains"}]}
        stmt = select(Role)
        stmt = apply_filters(Role, stmt, filters)
        session.add(Role(id="r_or", name="R1", description="D1"))
        await session.commit()
        result = await session.execute(stmt)
        items = result.scalars().all()
        assert len(items) >= 1

    async def test_should_count_records_without_explicit_session(self, repo):

        await repo.persist_record({"id": "c_no_sess", "name": "C_NS", "description": "D"})
        result = await repo.count_records()
        assert result >= 1

    async def test_should_check_exists_by_id_without_explicit_session(self, repo):
        await repo.persist_record({"id": "e_no_sess", "name": "E_NS", "description": "D"})
        result = await repo.exists_by_id(["e_no_sess"])
        assert "e_no_sess" in result["exists"]

    async def test_apply_filters_comparison_operators_extended(self, session):
        filters = {
            "andRules": [
                {"key": "price", "search": 10.0, "qt": "gte"},
                {"key": "price", "search": 100.0, "qt": "lte"},
                {"key": "price", "search": 5.0, "qt": "gt"},
                {"key": "price", "search": 200.0, "qt": "lt"},
            ]
        }
        stmt = select(Product)
        stmt = apply_filters(Product, stmt, filters)
        session.add(Product(id="p_ext_1", name="P1", sku="S_EXT_1", category="C", price=50.0, stock=10, description="D"))
        await session.commit()
        result = await session.execute(stmt)
        items = result.scalars().all()
        assert len(items) >= 1

    async def test_apply_filters_or_rules_equals_extended(self, session):
        filters = {
            "orRules": [{"key": "name", "search": "P_EXT_OR", "qt": "equals"}, {"key": "sku", "search": "S_EXT_OR", "qt": "contains"}]
        }
        stmt = select(Product)
        stmt = apply_filters(Product, stmt, filters)
        session.add(Product(id="p_ext_or", name="P_EXT_OR", sku="S_EXT_OR", category="C", price=50.0, stock=10, description="D"))
        await session.commit()
        result = await session.execute(stmt)
        items = result.scalars().all()
        assert len(items) >= 1
