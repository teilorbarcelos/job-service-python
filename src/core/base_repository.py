from typing import Generic, TypeVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.helpers.repository_helpers import apply_filters, apply_includes, apply_ordering, model_to_dict
from src.infra.database.base import Base
from src.modules.audit.audit_context import audit_json_dumps, set_audit_data

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, model: type[T], session_factory):
        self.model = model
        self.session_factory = session_factory

    async def find_one_by_query(
        self, query: dict, include: dict = None, session: AsyncSession = None, include_deleted: bool = False
    ) -> dict | None:
        stmt = select(self.model).filter_by(**query)
        stmt = apply_includes(self.model, stmt, include)

        joined_models = set()
        stmt = apply_filters(self.model, stmt, {"ignoreDefaultFilters": True, "includeDeleted": include_deleted}, joined_models)

        async def _exec(s):
            result = await s.execute(stmt)
            obj = result.scalar_one_or_none()
            return model_to_dict(obj)

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)

    async def find_one_by_id(
        self, id: str, include: dict = None, session: AsyncSession = None, include_deleted: bool = False
    ) -> dict | None:
        return await self.find_one_by_query({"id": id}, include=include, session=session, include_deleted=include_deleted)

    async def search_all(self, filters=None, include: dict = None, ordering=None, session: AsyncSession = None) -> list[dict]:
        stmt = select(self.model)
        joined_models = set()
        stmt = apply_filters(self.model, stmt, filters, joined_models)
        stmt = apply_ordering(self.model, stmt, ordering, joined_models)
        stmt = apply_includes(self.model, stmt, include)

        async def _exec(s):
            result = await s.execute(stmt)
            items = result.scalars().all()
            return [model_to_dict(item) for item in items]

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)

    async def count_records(self, filters=None, session: AsyncSession = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        joined_models = set()
        stmt = apply_filters(self.model, stmt, filters, joined_models)

        if session:
            result = await session.execute(stmt)
            return result.scalar() or 0
        async with self.session_factory() as local_session:
            result = await local_session.execute(stmt)
            return result.scalar() or 0

    async def persist_record(self, data: dict, session: AsyncSession = None) -> dict:
        set_audit_data(table_name=self.model.__tablename__, diff_value=audit_json_dumps({"action": "create", "data": data}))
        instance = self.model(**data)
        if session:
            session.add(instance)
            await session.flush()
            await session.refresh(instance)
            return model_to_dict(instance)
        async with self.session_factory() as local_session:
            local_session.add(instance)
            await local_session.commit()
            await local_session.refresh(instance)
            return model_to_dict(instance)

    async def update_record_details(self, id: str, data: dict, session: AsyncSession = None) -> dict | None:
        set_audit_data(table_name=self.model.__tablename__)

        async def _exec(s):

            old_obj = await s.get(self.model, id)
            if old_obj:
                old_data = model_to_dict(old_obj)
                set_audit_data(diff_value=audit_json_dumps({"before": old_data, "after": data}))

            stmt = update(self.model).where(self.model.id == id).values(**data)
            await s.execute(stmt)
            if not session:
                await s.commit()
            return await self.find_one_by_id(id, session=s, include_deleted=True)

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)

    async def activate_record(self, id: str, session: AsyncSession = None):
        return await self.update_record_details(id, {"active": True}, session=session)

    async def deactivate_record(self, id: str, session: AsyncSession = None):
        return await self.update_record_details(id, {"active": False}, session=session)

    async def soft_delete_record(self, id: str, session: AsyncSession = None):
        import datetime

        return await self.update_record_details(
            id, {"is_deleted": True, "deleted_at": datetime.datetime.now(), "active": False}, session=session
        )

    async def search_paginated(self, pageable: dict, filters=None, include=None, ordering=None, session: AsyncSession = None) -> dict:
        page = pageable.get("page", 0)
        size = pageable.get("size", 10)
        skip = page * size

        joined_models = set()
        stmt = select(self.model, func.count().over().label("total_count")).offset(skip).limit(size)
        stmt = apply_filters(self.model, stmt, filters, joined_models)
        stmt = apply_ordering(self.model, stmt, ordering, joined_models)
        stmt = apply_includes(self.model, stmt, include)

        async def _exec(s):
            items_result = await s.execute(stmt)
            rows = items_result.all()
            total = rows[0].total_count if rows else 0
            items = [model_to_dict(row[0]) for row in rows]
            return {"items": items, "total": total, "page": page, "size": size}

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)

    async def exists_by_id(self, ids: list[str], session: AsyncSession = None) -> dict:
        stmt = select(self.model.id).where(self.model.id.in_(ids))

        async def _exec(s):
            result = await s.execute(stmt)
            found = [r[0] for r in result.all()]
            missing = [id for id in ids if id not in found]
            return {"exists": found, "missing": missing}

        if session:
            return await _exec(session)
        async with self.session_factory() as local_session:
            return await _exec(local_session)

    async def persist_many(self, records: list, session: AsyncSession = None):
        set_audit_data(table_name=self.model.__tablename__, diff_value=audit_json_dumps({"action": "create_many", "count": len(records)}))
        instances = [self.model(**r) for r in records]
        if session:
            session.add_all(instances)
            await session.flush()
            return [model_to_dict(i) for i in instances]
        async with self.session_factory() as local_session:
            local_session.add_all(instances)
            await local_session.commit()
            return [model_to_dict(i) for i in instances]
