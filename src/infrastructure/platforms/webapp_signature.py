r"""Проверка подписи init data мини-приложения (BR-007).

Криптоядро ОДИНАКОВО у Telegram и MAX (specs/002-platform-deep-dive §3):

    secret_key = HMAC_SHA256(key=b"WebAppData", msg=bot_token)
    expected   = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
    valid      = constant_time_eq(expected, hash)

где ``data_check_string`` — пары ``key=value`` (все, КРОМЕ ``hash``),
отсортированные по ключу и соединённые '\\n'. Значения берутся
URL-декодированными. Токен и init data — секреты, не логировать.

Различия платформ (Ed25519 у Telegram, отдельная формула requestContact у MAX)
здесь НЕ реализуются — для базовой проверки initData ядро общее.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping
from urllib.parse import parse_qsl

_WEBAPP_DATA_KEY = b"WebAppData"


def verify_init_data(
    token: str,
    init_data: str,
    *,
    max_age_seconds: int,
    now: int | None = None,
) -> Mapping[str, str] | None:
    """Возвращает провалидированные пары init data или None (подпись/срок неверны)."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(_WEBAPP_DATA_KEY, token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    if max_age_seconds > 0 and not _fresh(pairs.get("auth_date"), max_age_seconds, now):
        return None
    return pairs


def _fresh(auth_date: str | None, max_age_seconds: int, now: int | None) -> bool:
    if auth_date is None:
        return True  # поле опционально; при отсутствии возраст не проверяем
    try:
        issued = int(auth_date)
    except ValueError:
        return False
    current = now if now is not None else int(time.time())
    return current - issued <= max_age_seconds  # допускаем небольшой clock skew (будущее)
