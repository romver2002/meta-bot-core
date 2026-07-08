"""Валидация init data MAX Web App (BR-007).

Фронт передаёт значение ``WebAppData`` (== ``window.WebApp.initData``) — плоскую
query-строку. Внешние поля фрагмента ``WebAppPlatform``/``WebAppVersion`` в
подпись НЕ входят и на backend не приходят. Отдельная формула ``requestContact``
(проверка телефона) — другая возможность, здесь не реализуется.
"""

from __future__ import annotations

from collections.abc import Mapping

from infrastructure.platforms.webapp_signature import verify_init_data


def validate_max_init_data(
    token: str, init_data: str, *, max_age_seconds: int, now: int | None = None
) -> Mapping[str, str] | None:
    return verify_init_data(token, init_data, max_age_seconds=max_age_seconds, now=now)
