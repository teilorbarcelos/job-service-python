from fastapi import Header, HTTPException, Request

from src.infra.auth.auth_provider import auth_provider
from src.infra.redis.redis_provider import redis_provider
from src.shared.config import messages


async def check_auth(request: Request, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)

    token = authorization.replace("Bearer ", "").strip().strip('"')

    payload = auth_provider.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail=messages.INVALID_OR_EXPIRED_TOKEN)

    user_id = payload.get("id")
    if not user_id or not await redis_provider.is_session_valid(user_id, token):
        raise HTTPException(status_code=401, detail=messages.SESSION_REVOKED)

    ver = payload.get("ver")
    if ver is not None:
        cached_ver = None
        try:
            cached_ver = await redis_provider.get_session_version(user_id)
        except Exception:
            pass
        if cached_ver is not None and cached_ver != ver:
            await redis_provider.remove_token_from_session(user_id, token)
            raise HTTPException(status_code=401, detail=messages.SESSION_EXPIRED)

    request.state.user = payload

    return payload
