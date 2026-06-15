import time

import redis.asyncio as redis

from src.infra.redis.redis_provider_interface import RedisProviderInterface
from src.shared.config.settings import settings


class RedisProvider(RedisProviderInterface):
    def __init__(self):
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )

    async def get(self, key: str):
        return await self.client.get(key)

    async def setex(self, key: str, time: int, value: str):
        return await self.client.setex(key, time, value)

    async def incr(self, key: str):
        return await self.client.incr(key)

    async def set_session(self, user_id: str, tokens: list, ttl: int = 7 * 24 * 3600):
        key = f"user:sessions:{user_id}"
        mapping = {token: time.time() for token in tokens}
        await self.client.zadd(key, mapping)
        await self.client.expire(key, ttl)

    async def is_session_valid(self, user_id: str, token: str) -> bool:
        key = f"user:sessions:{user_id}"
        score = await self.client.zscore(key, token)
        return score is not None

    async def remove_token_from_session(self, user_id: str, token: str):
        key = f"user:sessions:{user_id}"
        await self.client.zrem(key, token)

    async def invalidate_sessions(self, user_id: str):
        key = f"user:sessions:{user_id}"
        await self.client.delete(key)

    async def set_permissions(self, user_id: str, permissions: str, ttl: int = 60):
        key = f"user:permissions:{user_id}"
        await self.client.setex(key, ttl, permissions)

    async def get_permissions(self, user_id: str):
        key = f"user:permissions:{user_id}"
        return await self.client.get(key)

    async def invalidate_permissions(self, user_id: str):
        key = f"user:permissions:{user_id}"
        await self.client.delete(key)

    async def get_session_version(self, user_id: str):
        val = await self.client.get(f"user:session_version:{user_id}")
        return int(val) if val else None

    async def set_session_version(self, user_id: str, version: int, ttl: int = 3600):
        await self.client.setex(f"user:session_version:{user_id}", ttl, str(version))

    async def invalidate_session_version(self, user_id: str):
        await self.client.delete(f"user:session_version:{user_id}")

    async def is_locked(self, identifier: str) -> bool:
        try:
            key = f"lockout:{identifier}"
            val = await self.client.get(key)
            if val is None:
                return False
            return int(val) >= 5
        except Exception:
            return False

    async def increment_lockout(self, identifier: str):
        key = f"lockout:{identifier}"
        attempts = await self.client.incr(key)
        if attempts == 1:
            await self.client.expire(key, 60)
        elif attempts == 2:
            await self.client.expire(key, 300)
        elif attempts == 3:
            await self.client.expire(key, 3600)
        else:
            await self.client.expire(key, 86400)
        return attempts

    async def reset_lockout(self, identifier: str):
        key = f"lockout:{identifier}"
        await self.client.delete(key)


redis_provider = RedisProvider()
