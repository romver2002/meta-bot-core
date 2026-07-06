#!/usr/bin/env python3
"""Сводка по телеметрии чтения базы знаний (.claude/kb-usage.log).

Отвечает на главный вопрос пилота фактами, а не мнением:
  - какая доля сессий вообще открывала базу;
  - какая доля читала current/active-context.md (соблюдение протокола AGENTS.md);
  - какие файлы читаются чаще всего;
  - какие файлы МЕРТВЫ (ноль чтений за окно) — кандидаты на слияние/удаление.

Запуск: python scripts/kb_usage_report.py [--days 30] [--root PATH]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

LOG_REL = Path(".claude") / "kb-usage.log"
PROTOCOL_FILE = "memory-bank/current/active-context.md"


def parse_log(log_path: Path, since: datetime) -> list[tuple[datetime, str, str, str]]:
    events = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        try:
            stamp = datetime.fromisoformat(parts[0])
        except ValueError:
            continue
        if stamp >= since:
            events.append((stamp, parts[1], parts[2], parts[3]))
    return events


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30, help="окно отчёта в днях (по умолчанию 30)")
    parser.add_argument("--root", type=Path, default=None, help="корень репозитория")
    args = parser.parse_args(argv)

    root = args.root or (Path.cwd() if (Path.cwd() / "memory-bank").is_dir()
                         else Path(__file__).resolve().parent.parent)
    log_path = root / LOG_REL
    if not log_path.is_file():
        print(f"Лог {LOG_REL} не найден — телеметрия ещё не собиралась "
              f"(хуки настраиваются в .claude/settings.json).")
        return 1

    events = parse_log(log_path, datetime.now() - timedelta(days=args.days))
    if not events:
        print(f"За последние {args.days} дн. событий нет.")
        return 0

    sessions: set[str] = {s for _, s, e, _ in events if e == "session-start"}
    reads_by_session: dict[str, list[str]] = defaultdict(list)
    for _, session, event, rel in events:
        if event == "read":
            reads_by_session[session].append(rel)
    sessions |= set(reads_by_session)  # сессии без session-start (Codex, старые логи)

    total = len(sessions)
    with_reads = sum(1 for s in sessions if reads_by_session.get(s))
    with_protocol = sum(1 for s in sessions if PROTOCOL_FILE in reads_by_session.get(s, []))
    read_counter = Counter(rel for reads in reads_by_session.values() for rel in reads)

    print(f"Телеметрия базы знаний за {args.days} дн. (лог: {LOG_REL})")
    print(f"  Сессий: {total}")
    print(f"  Открывали базу: {with_reads} ({with_reads * 100 // max(total, 1)}%)")
    print(f"  Читали current/active-context.md (протокол): "
          f"{with_protocol} ({with_protocol * 100 // max(total, 1)}%)")

    print("\nТоп читаемых файлов:")
    for rel, count in read_counter.most_common(10):
        print(f"  {count:>4}  {rel}")

    bank = root / "memory-bank"
    dead = sorted(
        path.relative_to(root).as_posix()
        for path in bank.rglob("*.md")
        if path.relative_to(root).as_posix() not in read_counter
    )
    if dead:
        print(f"\nМёртвые файлы (0 чтений за {args.days} дн.) — кандидаты на слияние/удаление:")
        for rel in dead:
            print(f"  {rel}")
    else:
        print("\nМёртвых файлов нет — читается вся база.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
