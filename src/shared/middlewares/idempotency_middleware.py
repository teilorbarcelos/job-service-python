import hashlib
import json

from fastapi import Request
from fastapi.responses import JSONResponse

from src.infra.redis.redis_provider import redis_provider

IDEMPOTENCY_TTL = 24 * 3600
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:16]


async def idempotency_middleware(request: Request, call_next):
    if request.method not in WRITE_METHODS:
        return await call_next(request)

    idem_key = request.headers.get("Idempotency-Key", "")
    if not idem_key:
        return await call_next(request)

    cache_key = f"idem:{idem_key}"
    body_bytes = await request.body()
    body_hash = _hash_body(body_bytes)

    cached = await redis_provider.get(cache_key)
    if cached is not None:
        try:
            cached_data = json.loads(cached)
            if cached_data.get("body_hash") != body_hash:
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "Conflict",
                        "message": "Idempotency-Key already used with a different request body",
                        "idempotency_key": idem_key,
                    },
                )
            return JSONResponse(
                status_code=cached_data["status"],
                content=cached_data.get("response_body"),
                headers=cached_data.get("headers", {}),
            )
        except (json.JSONDecodeError, KeyError):
            pass

    response = await call_next(request)

    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    cached_value = json.dumps(
        {
            "body_hash": body_hash,
            "status": response.status_code,
            "response_body": json.loads(response_body) if response_body else None,
            "headers": dict(response.headers),
        }
    )
    await redis_provider.setex(cache_key, IDEMPOTENCY_TTL, cached_value)

    async def _response_body():
        yield response_body

    response.body_iterator = _response_body()
    response.headers["X-Idempotency-Key"] = idem_key
    return response
