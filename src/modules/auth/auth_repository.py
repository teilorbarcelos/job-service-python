from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.base_repository import BaseRepository, model_to_dict
from src.infra.database.db import SessionLocal
from src.infra.database.models import Auth, Role, RoleFeature, User


class AuthRepository(BaseRepository[Auth]):
    def __init__(self):
        super().__init__(model=Auth, session_factory=SessionLocal)

    async def find_first_with_user(self, email: str):
        async with self.session_factory() as session:
            stmt = (
                select(Auth)
                .join(User)
                .where(User.email == email)
                .options(selectinload(Auth.user).selectinload(User.role).selectinload(Role.role_features).selectinload(RoleFeature.feature))
            )
            result = await session.execute(stmt)
            auth = result.scalar_one_or_none()
            if not auth:
                return None

            auth_dict = model_to_dict(auth)

            if auth.user:
                user_dict = model_to_dict(auth.user)
                if auth.user.role:
                    role_dict = model_to_dict(auth.user.role)
                    role_dict["role_features"] = [
                        {**model_to_dict(rf), "feature_name": rf.feature.name if rf.feature else None}
                        for rf in auth.user.role.role_features
                    ]
                    user_dict["role"] = role_dict
                auth_dict["user"] = user_dict

            return auth_dict
