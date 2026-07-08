"""Валидация init data Telegram Web App (BR-007).

Telegram: исключается только ``hash``; поле ``signature`` (Bot API 8.0+)
ОСТАЁТСЯ в data_check_string (его покрывает серверный hash). Сторонний путь
Ed25519 (без токена) — отдельная возможность, пока не реализован.
"""

from __future__ import annotations

from collections.abc import Mapping

from infrastructure.platforms.webapp_signature import verify_init_data


def validate_telegram_init_data(
    token: str, init_data: str, *, max_age_seconds: int, now: int | None = None
) -> Mapping[str, str] | None:
    return verify_init_data(token, init_data, max_age_seconds=max_age_seconds, now=now)
