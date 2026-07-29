"""RedisIdempotency: короткий ключ «в работе» и продление после исполнения (ADR-0019)."""

from __future__ import annotations

from typing import Any

import pytest

from application.ports.idempotency import Reservation
from infrastructure.cache.redis_idempotency import RedisIdempotency

pytestmark = pytest.mark.unit

KEY = "events:bot-1:e-1"
IN_FLIGHT_TTL, DONE_TTL = 120, 86400


class FakeRedis:
    """Минимальный SET NX EX / GET / DELETE — как их видит адаптер (значения в bytes)."""

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.ttl: dict[str, int] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int = 0) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value.encode()
        self.ttl[key] = ex
        return True

    async def get(self, key: str) -> bytes | None:
        return self.values.get(key)

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self.values:
            return False
        self.ttl[key] = seconds
        return True

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)
        self.ttl.pop(key, None)


def _idempotency(client: FakeRedis) -> RedisIdempotency:
    return RedisIdempotency(
        client,  # type: ignore[arg-type] — FakeRedis повторяет используемую часть клиента
        ttl_seconds=DONE_TTL,
        in_flight_ttl_seconds=IN_FLIGHT_TTL,
    )


async def test_reserved_key_lives_short_until_confirmed() -> None:
    client = FakeRedis()
    idempotency = _idempotency(client)

    assert await idempotency.reserve(KEY) is Reservation.ACQUIRED
    assert client.ttl[KEY] == IN_FLIGHT_TTL  # убьют процесс — ключ истечёт сам

    await idempotency.confirm(KEY)
    assert client.ttl[KEY] == DONE_TTL


async def test_second_attempt_sees_in_flight_then_done() -> None:
    """Параллельный ретрай — «в работе», ретрай после исполнения — «дубль»."""
    idempotency = _idempotency(FakeRedis())

    await idempotency.reserve(KEY)
    assert await idempotency.reserve(KEY) is Reservation.IN_FLIGHT

    await idempotency.confirm(KEY)
    assert await idempotency.reserve(KEY) is Reservation.DONE


async def test_forgotten_key_can_be_reserved_again() -> None:
    idempotency = _idempotency(FakeRedis())

    await idempotency.reserve(KEY)
    await idempotency.forget(KEY)

    assert await idempotency.reserve(KEY) is Reservation.ACQUIRED


async def test_key_expired_between_set_and_get_is_taken_not_called_duplicate() -> None:
    """Гонка «ключ истёк ровно между SET NX и GET» не должна выглядеть дублем."""
    client = FakeRedis()
    idempotency = _idempotency(client)
    await idempotency.reserve(KEY)

    original_get = client.get

    async def expiring_get(key: str, *args: Any, **kwargs: Any) -> bytes | None:
        await client.delete(key)  # TTL истёк ровно сейчас
        client.get = original_get  # type: ignore[method-assign]
        return None

    client.get = expiring_get  # type: ignore[method-assign]

    assert await idempotency.reserve(KEY) is Reservation.ACQUIRED


async def test_touch_renews_lease_of_running_execution() -> None:
    """Пока исполнение живо, аренда продлевается — короткий TTL не истекает под ним."""
    client = FakeRedis()
    idempotency = _idempotency(client)
    await idempotency.reserve(KEY)
    client.ttl[KEY] = 5  # почти истёк

    await idempotency.touch(KEY)

    assert client.ttl[KEY] == IN_FLIGHT_TTL


async def test_legacy_key_counts_as_done_not_in_flight() -> None:
    """Ключ прежнего формата ("1" от first_time) — дубль, а не «в работе»."""
    client = FakeRedis()
    idempotency = _idempotency(client)
    await idempotency.first_time(KEY)

    assert await idempotency.reserve(KEY) is Reservation.DONE


async def test_webhook_path_keeps_single_ttl() -> None:
    """first_time (вебхуки, ADR-0004) не меняется: один ключ, полный TTL."""
    client = FakeRedis()
    idempotency = _idempotency(client)

    assert await idempotency.first_time(KEY) is True
    assert await idempotency.first_time(KEY) is False
    assert client.ttl[KEY] == DONE_TTL
