from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.base_repository import BaseRepository, model_to_dict
from src.infra.database.db import SessionLocal
from src.infra.database.models import Role


class RoleRepository(BaseRepository[Role]):
    def __init__(self):
        super().__init__(model=Role, session_factory=SessionLocal)

    async def find_one_by_id(self, id: str, include: dict = None, session=None, include_deleted: bool = False):
        async def _exec(s):
            stmt = select(Role).where(Role.id == id).options(selectinload(Role.role_features))
            result = await s.execute(stmt)
            role = result.scalar_one_or_none()
            if not role:
                return None

            role_dict = model_to_dict(role)
            role_dict["RoleFeature"] = [model_to_dict(rf) for rf in role.role_features]
            return role_dict

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)
