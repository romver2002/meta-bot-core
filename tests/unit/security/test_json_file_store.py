"""Dev-хранилища .secrets/ (json_file_store): атомарность, изоляция, контракт ошибок."""

from __future__ import annotations

from pathlib import Path

import pytest

from application.errors import ApplicationError
from infrastructure.security.file_notification_targets import FileNotificationTargets

pytestmark = pytest.mark.unit


async def test_store_and_resolve_isolated_by_bot(tmp_path: Path) -> None:
    targets = FileNotificationTargets(str(tmp_path / "targets.json"))

    await targets.store("bot-1", "admin", "chat-1")
    await targets.store("bot-2", "admin", "chat-2")

    assert await targets.resolve("bot-1", "admin") == "chat-1"
    assert await targets.resolve("bot-2", "admin") == "chat-2"
    assert await targets.resolve("bot-1", "developer") is None
    assert await targets.resolve("ghost", "admin") is None


async def test_store_overwrites_and_leaves_no_tmp_leftover(tmp_path: Path) -> None:
    path = tmp_path / "targets.json"
    targets = FileNotificationTargets(str(path))

    await targets.store("bot-1", "admin", "old")
    await targets.store("bot-1", "admin", "new")

    assert await targets.resolve("bot-1", "admin") == "new"
    leftover = [p.name for p in tmp_path.iterdir()]  # noqa: ASYNC240 — проверка каталога в unit-тесте
    assert leftover == ["targets.json"]  # атомарная запись не оставила tmp-файла


async def test_corrupted_file_raises_application_error(tmp_path: Path) -> None:
    path = tmp_path / "targets.json"
    path.write_text("{битый json", encoding="utf-8")
    targets = FileNotificationTargets(str(path))

    # Контракт порта: инфраструктурный сбой — всегда ApplicationError,
    # чтобы best-effort-потребитель (блок notify) пережил его штатно.
    with pytest.raises(ApplicationError):
        await targets.resolve("bot-1", "admin")
    with pytest.raises(ApplicationError):
        await targets.store("bot-1", "admin", "chat-1")
