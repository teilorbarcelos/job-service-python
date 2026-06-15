"""Async Redis singleton for the job runner.

This module owns a single `redis.asyncio.Redis` connection for the
whole job runner. Health checks and any other Redis consumer
(jobs that need caching, locks, etc.) acquire the client via
`get_client()`.

The client is created lazily on first call. The constructor is
chosen at runtime based on the value of `settings.redis_host`:

- If it starts with `redis://` or `rediss://` → `redis.from_url(...)`
- Otherwise → `redis.Redis(host=..., port=..., password=..., db=...)`

This dual-path lets the job service reuse the backend-python .env
without modification (the original uses `REDIS_HOST=redis://:@localhost:6379`,
which is a URL) while also supporting the explicit host/port form.
"""

from __future__ import annotations

import redis.asyncio as redis

from src.shared.config.settings import settings

_client: redis.Redis | None = None


def _is_url(host: str) -> bool:
    return host.startswith("redis://") or host.startswith("rediss://")


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        password = settings.redis_password or None
        timeout = settings.redis_command_timeout_s
        db = settings.redis_db
        if _is_url(settings.redis_host):
            _client = redis.from_url(
                settings.redis_host,
                password=password,
                db=db,
                socket_timeout=timeout,
                decode_responses=True,
            )
        else:
            _client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=password,
                db=db,
                socket_timeout=timeout,
                decode_responses=True,
            )
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def reset() -> None:
    """Clear the module-level client reference without closing.

    Use only in tests. Production code must call `await close()`.
    """
    global _client
    _client = None
