"""Сужение доверия сертификату Минцифры до MAX-адаптера.

Корень доверяется только в SSL-контексте MAX-клиента, а не в глобальном certifi
(иначе весь исходящий трафик — Telegram, OpenRouter — доверял бы гос-CA).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.platforms.max.tls import build_max_ssl_context

pytestmark = pytest.mark.unit

_CA = str(Path(__file__).resolve().parents[3] / "ops" / "certs" / "russian_trusted_root_ca.pem")
_MINCIFRY_CN = "Russian Trusted Root CA"


def _common_names(context: object) -> set[str]:
    names: set[str] = set()
    for cert in context.get_ca_certs():  # type: ignore[attr-defined]
        for rdn in cert.get("subject", ()):
            for key, value in rdn:
                if key == "commonName":
                    names.add(value)
    return names


def test_max_context_trusts_mincifry_when_bundle_present() -> None:
    names = _common_names(build_max_ssl_context(_CA))
    assert _MINCIFRY_CN in names  # MAX-соединения доверяют гос-CA


def test_default_context_does_not_trust_mincifry() -> None:
    # Без доп. bundle корня Минцифры в доверии нет — остальной трафик его не трогает.
    names = _common_names(build_max_ssl_context(None))
    assert _MINCIFRY_CN not in names


def test_missing_bundle_is_not_startup_error() -> None:
    # Отсутствие файла не роняет старт — контекст остаётся дефолтным.
    context = build_max_ssl_context("ops/certs/does-not-exist.pem")
    assert _MINCIFRY_CN not in _common_names(context)
