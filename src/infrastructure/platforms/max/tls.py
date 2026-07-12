"""TLS для MAX: доверие сертификату Минцифры ТОЛЬКО на соединениях с MAX.

``platform-api2.max.ru`` отдаёт цепочку под ``Russian Trusted Root CA``
(Минцифры), которого нет в стандартном bundle. Раньше корень дописывался в
глобальный ``certifi`` образа — это расширяло доверие на ВЕСЬ исходящий трафик
приложения (Telegram, OpenRouter и т.д.). Здесь корень добавляется в отдельный
``SSLContext``, который использует только ``MaxBotAdapter`` (получает свой
httpx-клиент из composition root); остальные клиенты остаются на дефолтном
``certifi``.
"""

from __future__ import annotations

import ssl
from pathlib import Path

import certifi
import httpx


def build_max_ssl_context(ca_bundle: str | None) -> ssl.SSLContext:
    """Дефолтное доверие (certifi) ПЛЮС доп. корень ``ca_bundle``, если файл есть.

    Отсутствие файла — не ошибка старта: контекст остаётся дефолтным, а TLS к
    MAX упадёт явной ошибкой при первом вызове (это честнее, чем молча падать
    из-за отсутствующего корня в глобальном bundle).
    """
    context = ssl.create_default_context(cafile=certifi.where())
    if ca_bundle and Path(ca_bundle).is_file():
        context.load_verify_locations(cafile=ca_bundle)
    return context


def build_max_http_client(*, ca_bundle: str | None, timeout: float) -> httpx.AsyncClient:
    """httpx-клиент MAX-адаптера с суженным доверием (см. модуль)."""
    return httpx.AsyncClient(timeout=timeout, verify=build_max_ssl_context(ca_bundle))
