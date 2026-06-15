"""PostgreSQL connection pool (asyncpg).

This module owns a single asyncpg.Pool for the whole job runner.
Jobs that need raw SQL access acquire connections from this pool
(`async with pool.acquire() as conn: ...`).

The pool is created lazily on first `get_pool()` call and closed
by `close_pool()` during graceful shutdown. `reset()` is a
sync helper for tests that clears the module-level reference without
actually closing the pool (use `close_pool()` in production).

The backend (backend-python) owns the schema and migrations. This
service only reads/writes the tables the backend has already created.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import asyncpg

from src.shared.config.settings import settings

_pool: asyncpg.Pool | None = None


def _normalize_dsn(url: str) -> str:
    """Convert SQLAlchemy-style URLs (postgresql+asyncpg://) to asyncpg-style.

    The backend-python service uses SQLAlchemy which writes
    `postgresql+asyncpg://...` in `.env`. asyncpg doesn't understand
    the `+asyncpg` suffix, so we strip it.
    """
    parsed = urlparse(url)
    if parsed.scheme == "postgresql+asyncpg":
        return urlunparse(parsed._replace(scheme="postgresql"))
    return url


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=_normalize_dsn(settings.database_url),
            min_size=2,
            max_size=settings.database_pool_max,
            command_timeout=settings.database_command_timeout_s,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def reset() -> None:
    """Clear the module-level pool reference without closing.

    Use only in tests. Production code must call `await close_pool()`.
    """
    global _pool
    _pool = None
