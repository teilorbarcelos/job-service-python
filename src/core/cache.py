import asyncio
import functools
import hashlib
import json
from collections.abc import Callable
from typing import Any

try:
    from src.infra.redis.redis_provider import redis_provider

    REDIS_AVAILABLE = True
except Exception:
    REDIS_AVAILABLE = False

_STAMPEDE_LOCKS: dict = {}


def _deserialize(value: str, serialize: bool) -> Any:
    if not serialize:
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _build_cache_key(key_prefix: str, func: Callable, args: tuple, kwargs: dict) -> str:
    key_parts = [key_prefix, func.__module__, func.__name__]
    key_parts.extend(str(a) for a in args)
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return hashlib.sha256(":".join(key_parts).encode()).hexdigest()[:32]


async def _wait_for_stampede(redis_key: str, lock_key: str, ttl: int, serialize: bool) -> Any | None:
    lock = _STAMPEDE_LOCKS.get(lock_key)
    if not lock or not lock.locked():
        return None
    try:
        async with asyncio.timeout(ttl / 2):
            cached_val = await redis_provider.get(redis_key)
            if cached_val is not None:
                return _deserialize(cached_val, serialize)
    except Exception:
        pass
    return None


async def _compute_and_cache(func: Callable, args: tuple, kwargs: dict, redis_key: str, ttl: int, serialize: bool) -> Any:
    lock_key = f"lock:{redis_key.replace('cache:', '', 1)}"
    if lock_key not in _STAMPEDE_LOCKS or not _STAMPEDE_LOCKS[lock_key].locked():
        _STAMPEDE_LOCKS[lock_key] = asyncio.Lock()

    async with _STAMPEDE_LOCKS[lock_key]:
        cached_val = await redis_provider.get(redis_key)
        if cached_val is not None:
            result = _deserialize(cached_val, serialize)
            if result is not None:
                _STAMPEDE_LOCKS.pop(lock_key, None)
                return result

        result = await func(*args, **kwargs)
        try:
            stored = json.dumps(result) if serialize else str(result)
            await redis_provider.setex(redis_key, ttl, stored)
        except Exception:
            pass
        finally:
            _STAMPEDE_LOCKS.pop(lock_key, None)
        return result


def cached(ttl: int = 60, key_prefix: str = "", serialize: bool = True):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not REDIS_AVAILABLE:
                return await func(*args, **kwargs)

            cache_key = _build_cache_key(key_prefix, func, args, kwargs)
            redis_key = f"cache:{cache_key}"
            lock_key = f"lock:{cache_key}"

            cached_val = await redis_provider.get(redis_key)
            if cached_val is not None:
                result = _deserialize(cached_val, serialize)
                if result is not None:
                    return result

            stampede_result = await _wait_for_stampede(redis_key, lock_key, ttl, serialize)
            if stampede_result is not None:
                return stampede_result

            return await _compute_and_cache(func, args, kwargs, redis_key, ttl, serialize)

        return wrapper

    return decorator


async def invalidate_cache(pattern: str = ""):
    if not REDIS_AVAILABLE:
        return
    try:
        keys = await redis_provider.client.keys(f"cache:{pattern}*")
        if keys:
            await redis_provider.client.delete(*keys)
    except Exception:
        pass
