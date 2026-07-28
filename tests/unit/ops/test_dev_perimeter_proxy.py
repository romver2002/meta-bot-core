"""Периметр dev-контура: что проходит наружу, а что обязано получить 404.

Цена ошибки в `_is_allowed` — не косметика: лишний разрешённый путь отдаёт
интернету Admin API без аутентификации, то есть управление всеми ботами
инстанса (ADR-0018, раздел «Риски»). Поэтому проверяем не только «пропускает
нужное», но и обходы: query-хвост, метод, регистр, обход по `..`.
"""

from __future__ import annotations

import pytest
from scripts.dev_perimeter_proxy import ALLOWED, _is_allowed

pytestmark = pytest.mark.unit

BOT = "2533666ef35e4cafbbd67ff73e214517"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"/webhooks/telegram/{BOT}"),
        ("POST", f"/webhooks/max/{BOT}"),
        ("POST", f"/api/bots/{BOT}/miniapp/auth"),
        ("POST", f"/api/bots/{BOT}/miniapp/result"),
        # Предполёт браузера mini app — без него POST из браузера не состоится.
        ("OPTIONS", f"/api/bots/{BOT}/miniapp/auth"),
        # Метод приходит как есть от клиента — регистр не должен ломать пропуск.
        ("post", f"/webhooks/max/{BOT}"),
    ],
)
def test_runtime_paths_pass(method: str, path: str) -> None:
    assert _is_allowed(method, path)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        # Управление ботами: подключение чужого токена, чтение и подмена сценария.
        ("POST", "/api/bots"),
        ("GET", "/api/bots"),
        ("GET", f"/api/bots/{BOT}"),
        ("GET", f"/api/bots/{BOT}/flow"),
        ("PUT", f"/api/bots/{BOT}/flow"),
        ("POST", f"/api/bots/{BOT}/publish"),
        # Увод доставки: events-токен и реестр ролей уведомлений.
        ("PUT", f"/api/bots/{BOT}/events-token"),
        ("PUT", f"/api/bots/{BOT}/notifications/owner"),
        # Приём внешних событий: снаружи не нужен — радар ходит внутрь хоста.
        ("POST", f"/api/bots/{BOT}/events"),
        # Внутренние: healthcheck наружу не выставляем (ADR-0018).
        ("GET", "/healthchecks/"),
        ("GET", "/"),
        ("GET", "/docs"),
        ("GET", "/openapi.json"),
    ],
)
def test_management_paths_are_closed(method: str, path: str) -> None:
    assert not _is_allowed(method, path)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        # Query-хвост не должен превращать закрытый путь в открытый.
        ("GET", f"/api/bots?next=/webhooks/telegram/{BOT}"),
        ("POST", f"/api/bots#/webhooks/max/{BOT}"),
        # Обход каталогом: точка не входит в алфавит идентификатора.
        ("POST", "/webhooks/telegram/../api/bots"),
        ("POST", f"/webhooks/telegram/{BOT}/../../api/bots"),
        # Метод: вебхук — только POST, чтение того же пути закрыто.
        ("GET", f"/webhooks/telegram/{BOT}"),
        ("DELETE", f"/webhooks/max/{BOT}"),
        # OPTIONS открыт только для mini app, не для вебхуков и не для /api вообще.
        ("OPTIONS", f"/webhooks/max/{BOT}"),
        ("OPTIONS", "/api/bots"),
        # Регистр пути значим: маршруты приложения регистрозависимы.
        ("POST", f"/Webhooks/telegram/{BOT}"),
        # Незакрытый хвост и вложенность.
        ("POST", f"/webhooks/telegram/{BOT}/"),
        ("POST", f"/api/bots/{BOT}/miniapp/auth/extra"),
        # Неизвестная платформа в пути.
        ("POST", f"/webhooks/whatsapp/{BOT}"),
        # Пустой идентификатор бота.
        ("POST", "/webhooks/telegram/"),
    ],
)
def test_bypasses_are_closed(method: str, path: str) -> None:
    assert not _is_allowed(method, path)


def test_allowlist_covers_only_documented_paths() -> None:
    """Список открытого наружу — ровно три пути ADR-0018 плюс предполёт mini app.

    Тест намеренно ломается при добавлении шаблона: расширение периметра —
    решение, а не правка по дороге.
    """
    assert sorted(ALLOWED) == ["OPTIONS", "POST"]
    assert len(ALLOWED["POST"]) == 3
    assert len(ALLOWED["OPTIONS"]) == 1
