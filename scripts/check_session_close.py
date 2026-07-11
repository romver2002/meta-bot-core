#!/usr/bin/env python3
"""Stop-hook Claude Code: значимая сессия не закрывается без следа в current/.

Логика: если в рабочей копии есть изменения вне memory-bank/ и .claude/
(сессия меняла проект), а в memory-bank/current/*.md не добавлено ни одной
строки с сегодняшней датой — возвращает decision:block с подсказкой
про `python scripts/mb_log.py`. Повторная остановка (stop_hook_active)
пропускается всегда — блок срабатывает максимум один раз.

Fail-safe: любая ошибка (нет git, не репозиторий, битый JSON) — молчаливый
выход 0, сессия не блокируется. Хук не имеет права ломать работу.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

IGNORED_PREFIXES = ("memory-bank/", ".claude/")
BLOCK_REASON = (
    "Сессия изменила файлы проекта, но в memory-bank/current/ нет записи с сегодняшней датой. "
    "Добавь итог одной командой: python scripts/mb_log.py done \"что сделано\" "
    "(расхождение база↔код: mb_log.py discrepancy <док> \"что расходится\"). "
    "Если задача незначимая — просто заверши ещё раз."
)


def run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True, timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def porcelain_paths(porcelain: str) -> list[str]:
    """Пути из `git status --porcelain` (для переименований — новый путь)."""
    paths = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip().strip('"'))
    return paths


def decide(porcelain: str, current_diff: str, today_iso: str) -> dict | None:
    """None — разрешить остановку; dict — блокировать с причиной."""
    meaningful = [p for p in porcelain_paths(porcelain)
                  if not p.startswith(IGNORED_PREFIXES)]
    if not meaningful:
        return None
    for line in current_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++") and today_iso in line:
            return None
    return {"decision": "block", "reason": BLOCK_REASON}


def main() -> int:
    try:
        # stdin читаем как UTF-8 явно: на русской Windows locale-декодирование
        # (cp1251) искажает кириллические пути в payload (cwd) → git не находит корень.
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if payload.get("stop_hook_active"):
            return 0
        cwd = Path(payload.get("cwd") or Path.cwd())

        toplevel = run_git(["rev-parse", "--show-toplevel"], cwd)
        if toplevel is None:
            return 0
        root = Path(toplevel.strip())

        porcelain = run_git(["status", "--porcelain"], root)
        # diff HEAD покрывает и застейдженное, и незастейдженное; плюс новые
        # (untracked) файлы current/ — через diff --no-index не усложняем,
        # их ловит porcelain как значимые только вне current/.
        current_diff = run_git(["diff", "HEAD", "--", "memory-bank/current"], root)
        if porcelain is None or current_diff is None:
            return 0

        verdict = decide(porcelain, current_diff, date.today().isoformat())
        if verdict is not None:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(verdict, ensure_ascii=False))
        return 0
    except Exception:  # noqa: BLE001 — хук обязан быть fail-safe
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
