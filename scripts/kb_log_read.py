#!/usr/bin/env python3
"""Телеметрия чтения базы знаний (PostToolUse/SessionStart-хук Claude Code).

Дописывает строку в локальный лог `.claude/kb-usage.log` (гитигнорится,
никуда не отправляется), когда агент читает файл базы. Формат строки:
ISO-время \t session_id \t событие \t путь.

Вызовы (настроены в .claude/settings.json):
  PostToolUse (matcher Read):  python scripts/kb_log_read.py
  SessionStart:                python scripts/kb_log_read.py --event session-start

Сводка — scripts/kb_usage_report.py.

Fail-safe: любые ошибки глотаются, всегда выход 0 — телеметрия не имеет
права мешать работе.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

LOG_REL = Path(".claude") / "kb-usage.log"
ROTATE_BYTES = 1_000_000
ROTATE_KEEP_LINES = 4000
ROOT_FILES = frozenset({"AGENTS.md", "CLAUDE.md"})


def tracked_rel_path(file_path: str, root: Path) -> str | None:
    """repo-относительный путь, если файл принадлежит базе знаний; иначе None."""
    try:
        rel = Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None
    if rel.startswith("memory-bank/") or rel in ROOT_FILES:
        return rel
    return None


def append_line(log_path: Path, line: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    if log_path.stat().st_size > ROTATE_BYTES:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        log_path.write_text("\n".join(lines[-ROTATE_KEEP_LINES:]) + "\n", encoding="utf-8")


def main() -> int:
    try:
        event = "session-start" if "--event" in sys.argv and "session-start" in sys.argv else "read"
        # UTF-8 явно: иначе на русской Windows кириллический file_path/cwd искажается (cp1251).
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        root = Path(payload.get("cwd") or Path.cwd())
        session = str(payload.get("session_id") or "-")

        if event == "read":
            file_path = (payload.get("tool_input") or {}).get("file_path", "")
            rel = tracked_rel_path(file_path, root)
            if rel is None:
                return 0
        else:
            rel = "-"

        stamp = datetime.now().isoformat(timespec="seconds")
        append_line(root / LOG_REL, f"{stamp}\t{session}\t{event}\t{rel}")
        return 0
    except Exception:  # noqa: BLE001 — телеметрия обязана быть fail-safe
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
