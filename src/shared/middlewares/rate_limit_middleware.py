import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from src.infra.auth.auth_provider import auth_provider
from src.infra.metrics.metric_service import metric_service
from src.infra.redis.redis_provider import redis_provider
from src.shared.config.settings import settings

RATE_LIMIT_LUA = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_req = tonumber(ARGV[3])
local cutoff = now - window

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])

if count >= max_req then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    local retry_after = 0
    if oldest[2] then
        retry_after = math.ceil(window + cutoff - tonumber(oldest[2]))
        if retry_after < 0 then retry_after = 0 end
    end
    return {0, count, retry_after}
end

local req_id = ARGV[4] or tostring(now)
redis.call('ZADD', KEYS[1], now, req_id)
redis.call('EXPIRE', KEYS[1], window)
return {1, count + 1, max_req - count - 1}
"""

BYPASS_PATHS = {"/v1/docs", "/v1/swagger.json", "/health", "/liveness", "/metrics"}

RATE_LIMIT_SHA = None


async def _check_rate_limit(key: str, limit: int, window: int) -> tuple[bool, int, int]:
    global RATE_LIMIT_SHA
    now = int(time.time())
    req_id = f"{now}:{os.urandom(4).hex()}"
    try:
        if RATE_LIMIT_SHA is None:
            RATE_LIMIT_SHA = await redis_provider.client.script_load(RATE_LIMIT_LUA)
        result = await redis_provider.client.evalsha(RATE_LIMIT_SHA, 1, key, str(now), str(window), str(limit), req_id)
        if not isinstance(result, (list, tuple)) or len(result) < 3:
            return True, 0, 0
        allowed, count, extra = result
        return bool(allowed), int(count), int(extra)
    except Exception:
        return True, 0, 0


def _extract_ip(request: Request) -> str:
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in ip:
        ip = ip.split(",")[0].strip()
    return ip


def _build_rate_limit_keys(ip: str, path: str, user_id: str | None) -> list[str]:
    keys = [
        f"rl:{ip}:{path}",
        f"rl:user:{user_id}:global" if user_id else None,
        "rl:global",
    ]
    return [k for k in keys if k]


def _rate_limit_exceeded_response(limit: int, window: int, extra: int) -> JSONResponse:
    try:
        metric_service.increment_counter("exceptions_total", type="HTTPException", status="429")
    except Exception:
        pass
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too Many Requests",
            "message": "Rate limit exceeded. Try again in some seconds.",
            "limit": limit,
            "window": f"{window}s",
        },
        headers={
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(extra) if extra > 0 else str(window),
            "Retry-After": str(max(1, extra)),
        },
    )


def _set_rate_limit_headers(response, limit: int, window: int, remaining: int):
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(window)


async def _handle_admin_bypass(request: Request, call_next):
    response = await call_next(request)
    _set_rate_limit_headers(response, settings.rate_limit_max, settings.rate_limit_window, settings.rate_limit_max)
    return response


async def _check_rate_limits(keys: list[str], limit: int, window: int) -> int:
    remaining = limit
    for key in keys:
        allowed, _, extra = await _check_rate_limit(key, limit, window)
        if not allowed:
            return -1
        remaining = min(remaining, extra)
    return remaining


async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in BYPASS_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    payload = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip().strip('"')
        payload = auth_provider.verify_token(token)
        if payload and payload.get("roleId") == "administrator":
            return await _handle_admin_bypass(request, call_next)

    limit = settings.rate_limit_max
    window = settings.rate_limit_window
    ip = _extract_ip(request)
    user_id = payload.get("id") if payload else None
    keys = _build_rate_limit_keys(ip, request.url.path, user_id)

    remaining = await _check_rate_limits(keys, limit, window)
    if remaining < 0:
        return _rate_limit_exceeded_response(limit, window, 0)

    response = await call_next(request)
    _set_rate_limit_headers(response, limit, window, remaining)
    return response
