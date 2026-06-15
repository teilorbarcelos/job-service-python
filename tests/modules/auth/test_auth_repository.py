import pytest
from src.modules.auth.auth_repository import AuthRepository
from src.infra.database.models import User, Role, Auth
from sqlalchemy import select


@pytest.mark.asyncio
async def test_auth_repository_find_with_user(session):
    repo = AuthRepository()

    session.add(Role(id="r1", name="R", description="D"))
    auth = Auth(id="a1", password="p")
    user = User(id="u1", email="find@test.com", name="N", id_role="r1", id_auth="a1")
    session.add_all([auth, user])
    await session.commit()

    result = await repo.find_first_with_user("find@test.com")
    assert result is not None
    assert result["user"]["email"] == "find@test.com"

    assert await repo.find_first_with_user("none@test.com") is None
