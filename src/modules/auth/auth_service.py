import datetime
import secrets

import bcrypt
from fastapi import HTTPException

from src.infra.auth.auth_provider import auth_provider
from src.infra.email.email_provider import email_provider
from src.infra.metrics.metric_service import metric_service
from src.infra.redis.redis_provider import redis_provider
from src.modules.audit.audit_events import emit_auth_event
from src.modules.auth.auth_repository import AuthRepository
from src.modules.auth.helpers.auth_helpers import format_permissions, format_user_auth_response
from src.shared.config import messages
from src.shared.utils.logging import get_logger

logger = get_logger("auth")


class AuthService:
    def __init__(self):
        self.repo = AuthRepository()

    async def _build_session_for_user(self, user: dict, session_version: int = 1) -> dict:
        role_data = user.get("role", {})
        if not role_data or not role_data.get("active", True):
            raise HTTPException(status_code=401, detail=messages.USER_ROLE_DISABLED)

        permissions = format_permissions(user)

        payload = {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "roleId": user.get("id_role"),
            "permissions": permissions,
        }

        tokens = auth_provider.generate_token_pair(payload, ver=session_version)
        await redis_provider.set_session(user["id"], [tokens["token"], tokens["refreshToken"]])
        await redis_provider.set_session_version(user["id"], session_version)
        if permissions:
            import json

            await redis_provider.set_permissions(user["id"], json.dumps(permissions), ttl=60)

        return {
            "message": messages.LOGIN_SUCCESSFUL,
            "valid": True,
            "token": tokens["token"],
            "refreshToken": tokens["refreshToken"],
            "user": format_user_auth_response(user, permissions),
        }

    async def _check_lockout(self, email: str):
        try:
            if await redis_provider.is_locked(email):
                raise HTTPException(status_code=401, detail=messages.ACCOUNT_LOCKED)
        except HTTPException:
            raise
        except Exception:
            pass

    async def _increment_lockout(self, email: str):
        try:
            await redis_provider.increment_lockout(email)
        except Exception:
            pass

    async def _reset_lockout(self, email: str):
        try:
            await redis_provider.reset_lockout(email)
        except Exception:
            pass

    async def _bump_session_version(self, user_id: str, auth_id: str):
        from sqlalchemy import update as sa_update

        async with self.repo.session_factory() as session:
            stmt = (
                sa_update(self.repo.model).where(self.repo.model.id == auth_id).values(session_version=self.repo.model.session_version + 1)
            )
            await session.execute(stmt)
            await session.commit()
        await redis_provider.invalidate_session_version(user_id)
        await redis_provider.invalidate_sessions(user_id)
        await redis_provider.invalidate_permissions(user_id)

    async def login(self, email: str, password: str):
        await self._check_lockout(email)

        auth_record = await self.repo.find_first_with_user(email)

        if not auth_record or not auth_record.get("user"):
            metric_service.increment_counter("auth_logins_total", status="failed")
            await emit_auth_event("login_failed", "unknown", error=messages.INVALID_CREDENTIALS)
            raise HTTPException(status_code=401, detail=messages.INVALID_CREDENTIALS)

        if not auth_record.get("active", True):
            metric_service.increment_counter("auth_logins_total", status="failed")
            await emit_auth_event("login_failed", auth_record.get("user", {}).get("id", "unknown"), error="Account disabled")
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_DISABLED)

        if auth_record.get("retries", 0) >= 5:
            metric_service.increment_counter("auth_logins_total", status="locked")
            await emit_auth_event("login_locked", auth_record.get("user", {}).get("id", "unknown"), error="Account locked")
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_LOCKED)

        if not bcrypt.checkpw(password.encode("utf-8"), auth_record.get("password", "").encode("utf-8")):
            new_retries = auth_record.get("retries", 0) + 1
            await self.repo.update_record_details(auth_record["id"], {"retries": new_retries})
            await self._increment_lockout(email)
            raise HTTPException(status_code=401, detail=messages.INVALID_CREDENTIALS)

        user = auth_record["user"]
        if not user.get("active", True):
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_DISABLED)

        await self.repo.update_record_details(auth_record["id"], {"retries": 0})
        await self._reset_lockout(email)

        metric_service.increment_counter("auth_logins_total", status="success")
        await emit_auth_event("login_success", user["id"], user.get("name", ""))
        session_version = auth_record.get("session_version", 1)
        return await self._build_session_for_user(user, session_version)

    async def get_me(self, token: str):
        if not token:
            raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)

        payload = auth_provider.verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)

        user_id = payload.get("id")
        if not user_id or not await redis_provider.is_session_valid(user_id, token):
            raise HTTPException(status_code=401, detail=messages.SESSION_REVOKED)

        auth_record = await self.repo.find_first_with_user(payload.get("email"))
        if not auth_record or not auth_record.get("active", True):
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_DISABLED)

        user = auth_record["user"]
        if not user.get("active", True):
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_DISABLED)

        session_version = auth_record.get("session_version", 1)
        return await self._build_session_for_user(user, session_version)

    async def refresh(self, refresh_token: str):
        payload = auth_provider.verify_token(refresh_token)
        if not payload:
            raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)

        auth_record = await self.repo.find_first_with_user(payload.get("email"))
        if not auth_record or not auth_record.get("active", True):
            raise HTTPException(status_code=401, detail=messages.ACCOUNT_DISABLED)

        user = auth_record["user"]
        if not await redis_provider.is_session_valid(user["id"], refresh_token):
            raise HTTPException(status_code=401, detail=messages.INVALID_REFRESH_TOKEN)

        await redis_provider.remove_token_from_session(user["id"], refresh_token)

        session_version = auth_record.get("session_version", 1)
        return await self._build_session_for_user(user, session_version)

    async def logout(self, token: str):
        payload = auth_provider.verify_token(token)
        if payload and payload.get("id"):
            await redis_provider.remove_token_from_session(payload["id"], token)
        return {"message": messages.LOGGED_OUT_SUCCESSFULLY}

    async def logout_all(self, token: str):
        payload = auth_provider.verify_token(token)
        if payload and payload.get("id"):
            auth_record = await self.repo.find_first_with_user(payload.get("email"))
            if auth_record and auth_record.get("user"):
                auth_id = auth_record.get("id")
                user_id = auth_record["user"]["id"]
                await self._bump_session_version(user_id, auth_id)
        return {"message": messages.ALL_SESSIONS_REVOKED}

    async def request_password_reset(self, email: str):
        auth_record = await self.repo.find_first_with_user(email)
        if not auth_record:
            raise HTTPException(status_code=404, detail=messages.EMAIL_NOT_FOUND)

        reset_token = secrets.token_urlsafe(32)
        hashed_token = bcrypt.hashpw(reset_token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await self.repo.update_record_details(
            auth_record["id"],
            {
                "request_password_token": hashed_token,
                "request_password_expiration": datetime.datetime.now() + datetime.timedelta(hours=1),
            },
        )

        user_id = auth_record.get("user", {}).get("id", "unknown")
        await emit_auth_event("password_reset_requested", user_id)

        try:
            email_provider.send_email(to=email, subject="Reset Password", body=reset_token)
        except Exception as e:
            logger.warning(f"Failed to send password reset email to {email}: {e}")

        return {"message": messages.RECOVERY_EMAIL_SENT}

    async def validate_password_reset_token(self, email: str, token: str):
        auth_record = await self.repo.find_first_with_user(email)
        if not auth_record:
            raise HTTPException(status_code=404, detail=messages.EMAIL_NOT_FOUND)

        stored_hash = auth_record.get("request_password_token")
        if not stored_hash:
            raise HTTPException(status_code=401, detail=messages.INVALID_RESET_TOKEN)

        try:
            if not bcrypt.checkpw(token.encode("utf-8"), stored_hash.encode("utf-8")):
                raise HTTPException(status_code=401, detail=messages.INVALID_RESET_TOKEN)
        except Exception:
            raise HTTPException(status_code=401, detail=messages.INVALID_RESET_TOKEN)

        if not auth_record.get("request_password_expiration") or auth_record["request_password_expiration"] < datetime.datetime.now():
            raise HTTPException(status_code=401, detail=messages.RESET_TOKEN_EXPIRED)

        return {"valid": True}

    async def change_password(self, email: str, token: str, new_password: str):
        await self.validate_password_reset_token(email, token)

        auth_record = await self.repo.find_first_with_user(email)
        user_id = auth_record["user"]["id"]
        auth_id = auth_record["id"]

        hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        await self.repo.update_record_details(
            auth_id,
            {
                "password": hashed,
                "password_algo": "bcrypt",
                "password_updated_at": datetime.datetime.now(),
                "request_password_token": None,
                "request_password_expiration": None,
            },
        )

        await self._bump_session_version(user_id, auth_id)
        await emit_auth_event("password_changed", user_id)

        return {"message": messages.PASSWORD_CHANGED_SUCCESSFULLY}


auth_service = AuthService()
