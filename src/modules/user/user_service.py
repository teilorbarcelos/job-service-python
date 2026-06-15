import datetime
from collections.abc import AsyncIterable

import bcrypt
from fastapi import HTTPException

from src.core.base_service import BaseService
from src.infra.database.db import get_session
from src.infra.database.models import Auth
from src.infra.email.email_provider import email_provider
from src.infra.metrics.metric_service import metric_service
from src.infra.redis.redis_provider import redis_provider
from src.modules.audit.audit_events import emit_user_event
from src.modules.auth.auth_repository import AuthRepository
from src.modules.user.user_repository import UserRepository
from src.shared.config import messages
from src.shared.config.settings import settings
from src.shared.utils.logging import get_logger

logger = get_logger("user")


class UserService(BaseService):
    def __init__(self):
        super().__init__(UserRepository())
        self.auth_repo = AuthRepository()

        self.allow_filters(
            [
                {"key": "name", "qt": "contains"},
                {"key": "email", "qt": "equals"},
                {"key": "active"},
                {"key": "role.name", "qt": "contains"},
                {"key": "created_at"},
            ]
        )

        self.allow_search([{"key": "name"}, {"key": "email"}, {"key": "role.name"}])

    def _is_first_admin(self, user: dict) -> bool:
        return user.get("email") == settings.first_user

    async def _bump_session_version(self, user_id: str, auth_id: str, session=None):
        if session is None:
            async with get_session() as s:
                await self._do_bump_session_version(user_id, auth_id, s)
        else:
            await self._do_bump_session_version(user_id, auth_id, session)

    async def _do_bump_session_version(self, user_id: str, auth_id: str, session):
        from sqlalchemy import update as sa_update

        stmt = sa_update(Auth).where(Auth.id == auth_id).values(session_version=Auth.session_version + 1)
        await session.execute(stmt)
        await session.flush()
        await redis_provider.invalidate_session_version(user_id)
        await redis_provider.invalidate_sessions(user_id)
        await redis_provider.invalidate_permissions(user_id)

    async def create(self, data: dict):
        email = data.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")

        async with get_session() as session:
            existing = await self.repo.find_one_by_query({"email": email}, session=session)
            if existing:
                raise HTTPException(status_code=400, detail="User already exists")

            auth = Auth(
                password=bcrypt.hashpw((data.get("password") or "default123").encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                password_algo="bcrypt",
            )
            session.add(auth)
            await session.flush()

            user_data = {
                "email": email,
                "name": data.get("name"),
                "phone": data.get("phone"),
                "document": data.get("document"),
                "id_role": data.get("id_role", "operator"),
                "id_auth": auth.id,
            }
            user_dict = await self.repo.persist_record(user_data, session=session)

            metric_service.increment_counter("users_created_total")
            await emit_user_event("created", user_dict["id"], data.get("name", ""))

            try:
                email_provider.send_email(to=email, subject="Welcome", body="...")
            except Exception as e:
                logger.warning(f"Failed to send welcome email to {email}: {e}")

            return user_dict

    async def update(self, id: str, data: dict):
        async with get_session() as session:
            user = await self.repo.find_one_by_id(id, session=session)
            if not user:
                raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)

            bump_version = False

            if "password" in data:
                hashed = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                if user.get("id_auth"):
                    auth_id = user["id_auth"]
                    await self.auth_repo.update_record_details(
                        auth_id,
                        {
                            "password": hashed,
                            "password_algo": "bcrypt",
                            "password_updated_at": datetime.datetime.now(),
                        },
                        session=session,
                    )
                    bump_version = True

            if "id_role" in data and data["id_role"] != user.get("id_role"):
                bump_version = True

            if not self._is_first_admin(user):
                update_data = {k: v for k, v in data.items() if k not in ("password",)}
                if update_data:
                    await self.repo.update_record_details(id, update_data, session=session)

            if bump_version and user.get("id_auth"):
                await self._bump_session_version(id, user["id_auth"], session=session)
            else:
                await redis_provider.invalidate_sessions(id)

            return await self.repo.find_one_by_id(id, session=session)

    async def delete(self, id: str):
        async with get_session() as session:
            user = await self.repo.find_one_by_id(id, session=session)
            if not user:
                raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)

            if self._is_first_admin(user):
                raise HTTPException(status_code=400, detail="O usuário administrador inicial não pode ser excluído.")

            anonymized_data = {
                "name": "Deleted User",
                "email": f"deleted-{id}@anonymized.local",
                "is_deleted": True,
                "deleted_at": datetime.datetime.now(),
                "active": False,
            }
            result = await self.repo.update_record_details(id, anonymized_data, session=session)
            await redis_provider.invalidate_sessions(id)
            await redis_provider.invalidate_session_version(id)
            await redis_provider.invalidate_permissions(id)
            return result

    async def set_status(self, id: str, active: bool):
        user = await self.repo.find_one_by_id(id)
        if not user:
            raise HTTPException(status_code=404, detail=messages.USER_NOT_FOUND)

        if not active and self._is_first_admin(user):
            raise HTTPException(status_code=400, detail="O usuário administrador inicial não pode ser desativado.")

        result = await super().set_status(id, active)
        if not active and user.get("id_auth"):
            await self._bump_session_version(id, user["id_auth"])
        else:
            await redis_provider.invalidate_sessions(id)
        return result

    async def export_pdf(self, query: dict) -> AsyncIterable[bytes]:
        import datetime

        from src.core.helpers.service_helpers import build_filter_and_order
        from src.infra.pdf.pdf_dto import PdfRequestDTO
        from src.infra.pdf.pdf_provider import pdf_provider

        params = build_filter_and_order(query, self._allowed_filters, self._allowed_search)

        users = await self.repo.search_all(filters=params["rules"], include={"role": True}, ordering=params["ordering"])

        now = datetime.datetime.now()
        local_time = now.strftime("%d/%m/%Y %H:%M:%S")

        users_data = []
        for u in users:
            role_dict = u.get("role")
            role_name = role_dict.get("name") if role_dict else None
            users_data.append(
                {
                    "id": u.get("id"),
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "phone": u.get("phone"),
                    "roleName": role_name,
                    "active": u.get("active"),
                }
            )

        pdf_data = {"title": "Relatório de Usuários", "generatedAt": local_time, "users": users_data}

        request_dto = PdfRequestDTO(template="user-list", data=pdf_data)

        return pdf_provider.generate_pdf(request_dto)


user_service = UserService()
