"""RedisIdempotency — реализация IdempotencyPort (SET NX EX, ADR-0004)."""

from __future__ import annotations

from redis.asyncio import Redis

from infrastructure.config import Settings


class RedisIdempotency:
    """Первый приём ставит ключ атомарно; повтор в пределах TTL — дубликат."""

    def __init__(self, client: Redis, *, ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> RedisIdempotency:
        return cls(
            Redis.from_url(settings.redis_url),
            ttl_seconds=settings.webhook_idempotency_ttl,
        )

    async def first_time(self, key: str) -> bool:
        return bool(await self._client.set(key, "1", nx=True, ex=self._ttl))

    async def forget(self, key: str) -> None:
        await self._client.delete(key)
