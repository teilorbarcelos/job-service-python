import pytest
from src.core.base_repository import BaseRepository
from src.infra.database.models import User, Role
from sqlalchemy import select


class UserRepo(BaseRepository[User]):
    def __init__(self, session_factory):
        super().__init__(model=User, session_factory=session_factory)


@pytest.mark.asyncio
class TestBaseRepositoryNested:
    async def test_should_filter_by_nested_attribute(self, session):

        role_admin = Role(id="admin", name="Administrator", description="Full access")
        role_user = Role(id="user", name="Regular User", description="Limited access")
        session.add_all([role_admin, role_user])
        await session.commit()

        user1 = User(id="u1", name="John Admin", email="john@test.com", id_role="admin")
        user2 = User(id="u2", name="Jane User", email="jane@test.com", id_role="user")
        session.add_all([user1, user2])
        await session.commit()

        repo = UserRepo(lambda: session)

        filters = {"andRules": [{"key": "role.name", "search": "Administrator", "qt": "equals"}]}
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, filters=filters, session=session)

        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John Admin"

    async def test_should_filter_by_nested_attribute_contains(self, session):
        role_admin = Role(id="admin", name="Administrator", description="Full access")
        session.add(role_admin)
        await session.commit()

        user = User(id="u1", name="John", email="john@test.com", id_role="admin")
        session.add(user)
        await session.commit()

        repo = UserRepo(lambda: session)

        filters = {"andRules": [{"key": "role.name", "search": "Admin", "qt": "contains"}]}
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, filters=filters, session=session)

        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John"

    async def test_should_order_by_nested_attribute(self, session):
        role_a = Role(id="a", name="A Role", description="D")
        role_b = Role(id="b", name="B Role", description="D")
        session.add_all([role_a, role_b])
        await session.commit()

        user1 = User(id="u1", name="User B", email="u1@test.com", id_role="b")
        user2 = User(id="u2", name="User A", email="u2@test.com", id_role="a")
        session.add_all([user1, user2])
        await session.commit()

        repo = UserRepo(lambda: session)

        ordering = {"orderBy": "role.name", "orderDirection": "asc"}
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, ordering=ordering, session=session)

        assert result["items"][0]["name"] == "User A"
        assert result["items"][1]["name"] == "User B"

        ordering = {"orderBy": "role.name", "orderDirection": "desc"}
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, ordering=ordering, session=session)

        assert result["items"][0]["name"] == "User B"
        assert result["items"][1]["name"] == "User A"

    async def test_should_filter_by_deep_nested_attribute(self, session):
        from src.infra.database.models import RoleFeature, Feature

        feature = Feature(id="f1", name="F1", description="D1")
        session.add(feature)

        role_admin = Role(id="admin2", name="Administrator 2", description="Full access")
        role_user = Role(id="user2", name="Regular User 2", description="Limited access")
        session.add_all([role_admin, role_user])
        await session.flush()

        rf = RoleFeature(id_role="admin2", id_feature="f1", view=True)
        session.add(rf)
        await session.commit()

        user1 = User(id="u1_deep", name="John Admin 2", email="john2@test.com", id_role="admin2")
        user2 = User(id="u2_deep", name="Jane User 2", email="jane2@test.com", id_role="user2")
        session.add_all([user1, user2])
        await session.commit()

        repo = UserRepo(lambda: session)

        filters = {"andRules": [{"key": "role.role_features.view", "search": True, "qt": "equals"}]}
        result = await repo.search_paginated(pageable={"page": 0, "size": 10}, filters=filters, session=session)

        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "John Admin 2"

        or_filters = {"orRules": [{"key": "role.role_features.view", "search": True, "qt": "equals"}]}
        result_or = await repo.search_paginated(pageable={"page": 0, "size": 10}, filters=or_filters, session=session)
        assert len(result_or["items"]) == 1
        assert result_or["items"][0]["name"] == "John Admin 2"

    async def test_build_nested_any_has_condition_operators(self, session):
        from src.core.helpers.repository_helpers import build_nested_any_has_condition

        cond_contains = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "contains", "f")
        assert cond_contains is not None

        cond_gte = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "gte", "f1")
        assert cond_gte is not None

        cond_lte = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "lte", "f1")
        assert cond_lte is not None

        cond_gt = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "gt", "f1")
        assert cond_gt is not None

        cond_lt = build_nested_any_has_condition(User, ["role", "role_features", "id_feature"], "lt", "f1")
        assert cond_lt is not None

        cond_none = build_nested_any_has_condition(User, ["role", "role_features", "non_existent"], "equals", "f1")
        assert cond_none is None

        cond_none_rel = build_nested_any_has_condition(User, ["role", "non_existent_rel", "id_feature"], "equals", "f1")
        assert cond_none_rel is None

    async def test_should_return_none_for_deeply_nested_invalid_key(self, session):
        from src.core.helpers.repository_helpers import get_attribute_and_join

        repo = UserRepo(lambda: session)
        attr, _ = get_attribute_and_join(User, select(User), "role.invalid_field", set())
        assert attr is None

    async def test_should_return_none_for_invalid_relationship_part(self, session):
        from src.core.helpers.repository_helpers import get_attribute_and_join

        repo = UserRepo(lambda: session)
        attr, _ = get_attribute_and_join(User, select(User), "invalid_rel.name", set())
        assert attr is None
