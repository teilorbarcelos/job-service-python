import pytest
from src.core.base_repository import BaseRepository
from src.infra.database.models import Role, Feature, RoleFeature
from sqlalchemy import select, Table, Column, String, MetaData


@pytest.mark.asyncio
async def test_base_repository_edge_cases(session):
    metadata = MetaData()
    mock_table = Table("mock", metadata, Column("id", String, primary_key=True))

    from src.core.helpers.repository_helpers import apply_ordering, get_attribute_and_join, apply_includes, apply_filters

    repo = BaseRepository(mock_table, lambda: session)
    stmt = select(mock_table)
    ordered_stmt = apply_ordering(mock_table, stmt, None)
    assert "ORDER BY" not in str(ordered_stmt)

    role_repo = BaseRepository(Role, lambda: session)
    attr, _ = get_attribute_and_join(Role, select(Role), "non_existent_field", set())
    assert attr is None

    attr, _ = get_attribute_and_join(Role, select(Role), "invalid_rel.name", set())
    assert attr is None

    included_stmt = apply_includes(Role, select(Role), {"invalid_rel": True})
    assert "SELECT" in str(included_stmt)

    mock_repo = BaseRepository(mock_table, lambda: session)
    stmt = apply_filters(mock_table, select(mock_table), None)
    assert "WHERE" not in str(stmt)

    cnt = await role_repo.count_records(session=session)
    assert isinstance(cnt, int)

    role_data = {"id": "session_role", "name": "Session", "description": "D"}
    await role_repo.persist_record(role_data, session=session)

    check = await role_repo.find_one_by_id("session_role", session=session)
    assert check["name"] == "Session"

    session.add(Role(id="r_list", name="ListRole", description="D"))
    session.add(Feature(id="f_list", name="ListFeat", description="D"))
    session.add(RoleFeature(id_role="r_list", id_feature="f_list", view=True))
    await session.flush()

    result = await role_repo.find_one_by_id("r_list", include={"role_features": True}, session=session)
    assert "role_features" in result
    assert isinstance(result["role_features"], list)
    assert len(result["role_features"]) == 1
