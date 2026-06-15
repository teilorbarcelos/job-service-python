from sqlalchemy import delete, select

from src.core.base_service import BaseService
from src.core.cache import invalidate_cache
from src.infra.database.db import get_session
from src.infra.database.models import Auth
from src.infra.redis.redis_provider import redis_provider
from src.modules.feature.feature_service import feature_service
from src.modules.role.models import RoleFeature

CACHE_PREFIX_ROLE = "role:"
from src.modules.role.role_repository import RoleRepository
from src.modules.user.models import User


class RoleService(BaseService):
    def __init__(self):
        super().__init__(RoleRepository())
        self.allow_filters([{"key": "name", "qt": "contains"}, {"key": "active"}, {"key": "created_at"}])
        self.allow_search([{"key": "name"}])

    async def list_features(self):
        return await feature_service.repo.search_all()

    async def create(self, data: dict):
        permissions = data.pop("permissions", [])
        if not data.get("id"):
            import re

            name = data.get("name", "")
            slug = name.lower().strip()
            slug = re.sub(r"[^\w\s-]", "", slug)
            slug = re.sub(r"[\s_-]+", "-", slug)
            data["id"] = slug

        async with get_session() as session:
            role = await self.repo.persist_record(data, session=session)
            if permissions:
                await self._sync_permissions(role["id"], permissions, session)
            await session.commit()
            await invalidate_cache(CACHE_PREFIX_ROLE)
            return await self.repo.find_one_by_id(role["id"])

    async def update(self, id: str, data: dict):
        permissions = data.pop("permissions", None)
        async with get_session() as session:
            await self.repo.update_record_details(id, data, session=session)
            if permissions is not None:
                await self._sync_permissions(id, permissions, session)

            if permissions is not None or "active" in data:
                await self._invalidate_users_with_role(id, session)

            await session.commit()
            await invalidate_cache(CACHE_PREFIX_ROLE)
            return await self.repo.find_one_by_id(id)

    async def delete(self, id: str):
        async with get_session() as session:
            result = await super().delete(id)
            await self._invalidate_users_with_role(id, session)
            await session.commit()
            await invalidate_cache(CACHE_PREFIX_ROLE)
            return result

    async def set_status(self, id: str, active: bool):
        async with get_session() as session:
            result = await super().set_status(id, active)
            await self._invalidate_users_with_role(id, session)
            await session.commit()
            await invalidate_cache(CACHE_PREFIX_ROLE)
            return result

    async def _invalidate_users_with_role(self, role_id: str, session):
        stmt = select(User.id, User.id_auth).where(User.id_role == role_id)
        result = await session.execute(stmt)
        rows = result.all()

        for row in rows:
            user_id = row[0]
            auth_id = row[1]
            await redis_provider.invalidate_sessions(user_id)
            await redis_provider.invalidate_session_version(user_id)
            await redis_provider.invalidate_permissions(user_id)
            if auth_id:
                auth_stmt = select(Auth).where(Auth.id == auth_id)
                auth_result = await session.execute(auth_stmt)
                auth_obj = auth_result.scalar_one_or_none()
                if auth_obj:
                    auth_obj.session_version += 1
        await session.flush()

    async def _sync_permissions(self, role_id: str, permissions: list, session):
        await session.execute(delete(RoleFeature).where(RoleFeature.id_role == role_id))

        new_features = []
        for p in permissions:
            new_features.append(
                RoleFeature(
                    id_role=role_id,
                    id_feature=p.get("id_feature"),
                    create=p.get("create", False),
                    view=p.get("view", False),
                    delete=p.get("delete", False),
                    activate=p.get("activate", False),
                )
            )

        if new_features:
            session.add_all(new_features)
        await session.flush()


role_service = RoleService()
