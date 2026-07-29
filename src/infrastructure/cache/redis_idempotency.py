"""RedisIdempotency — реализация IdempotencyPort (SET NX EX, ADR-0004, ADR-0019)."""

from __future__ import annotations

from redis.asyncio import Redis

from application.ports.idempotency import Reservation
from infrastructure.config import Settings

_IN_FLIGHT = "in-flight"
_DONE = "done"


class RedisIdempotency:
    """Первый приём ставит ключ атомарно; повтор в пределах TTL — дубликат.

    Значение ключа различает «в работе» и «выполнено»: незавершённая попытка
    живёт коротким TTL и после падения процесса истекает сама, а выполненная
    продлевается до полного TTL дедупа.
    """

    def __init__(self, client: Redis, *, ttl_seconds: int, in_flight_ttl_seconds: int) -> None:
        self._client = client
        self._ttl = ttl_seconds
        self._in_flight_ttl = in_flight_ttl_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> RedisIdempotency:
        return cls(
            Redis.from_url(settings.redis_url),
            ttl_seconds=settings.webhook_idempotency_ttl,
            in_flight_ttl_seconds=settings.events_inflight_ttl,
        )

    async def first_time(self, key: str) -> bool:
        return bool(await self._client.set(key, "1", nx=True, ex=self._ttl))

    async def reserve(self, key: str) -> Reservation:
        if await self._take(key):
            return Reservation.ACQUIRED
        state = await self._client.get(key)
        if state is None:
            # Ключ истёк между SET NX и GET — либо он наш, либо его уже
            # перехватила параллельная попытка.
            return Reservation.ACQUIRED if await self._take(key) else Reservation.IN_FLIGHT
        # «В работе» — только точный маркер. Всё остальное (в т.ч. ключ прежнего
        # формата "1" от first_time) считаем выполненным: fail-safe здесь —
        # не переотправлять, иначе получатель увидит карточку дважды.
        return Reservation.IN_FLIGHT if _text(state) == _IN_FLIGHT else Reservation.DONE

    async def touch(self, key: str) -> None:
        await self._client.expire(key, self._in_flight_ttl)

    async def confirm(self, key: str) -> None:
        await self._client.set(key, _DONE, ex=self._ttl)

    async def forget(self, key: str) -> None:
        await self._client.delete(key)

    async def _take(self, key: str) -> bool:
        return bool(await self._client.set(key, _IN_FLIGHT, nx=True, ex=self._in_flight_ttl))


def _text(value: object) -> str:
    """Клиент отдаёт bytes (decode_responses не включён) — сравниваем как текст."""
    return value.decode() if isinstance(value, bytes) else str(value)
