#!/usr/bin/env python3
"""Запись в current/ одной командой — для агентов и людей.

Вместо «открой файл, найди раздел, соблюди формат» — один вызов:

  python scripts/mb_log.py done "перенесён адаптер платежей на порт X"
  python scripts/mb_log.py focus "интеграция провайдера Y (релиз 1.2)"
  python scripts/mb_log.py next "контрактные тесты адаптера"
  python scripts/mb_log.py question "храним ли историю статусов заказа?"
  python scripts/mb_log.py debt "отчёты ходят в БД мимо портов (#98)"
  python scripts/mb_log.py problem "дублируется номер заказа" --impact "2-3/нед" --issue "#142"
  python scripts/mb_log.py discrepancy architecture/overview.md "в доке use case зовёт репозиторий напрямую"

Скрипт добавляет датированную запись в нужный раздел нужного файла current/,
поднимает version/updated и предупреждает о превышении бюджета длины
(лимиты — как в валидаторе, MB052).

Маппинг раздел→заголовок завязан на канонические заголовки current/-файлов
шаблона — единственная точка сопровождения при их переименовании.

Коды выхода: 0 — записано; 1 — файл/раздел не найден; 2 — некорректный вызов.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mb_lib  # noqa: E402
from mb_lib import split_document, touch  # noqa: E402

ACTIVE = "memory-bank/current/active-context.md"
PROGRESS = "memory-bank/current/progress.md"
BODY_WARN_LINES = 80  # согласовано с правилом MB052 валидатора


@dataclass(frozen=True)
class Target:
    file: str
    heading: str
    kind: str  # bullet | table


TARGETS: dict[str, Target] = {
    "focus": Target(ACTIVE, "Текущий фокус", "bullet"),
    "done": Target(ACTIVE, "Последние решения и договорённости", "bullet"),
    "next": Target(ACTIVE, "Следующие шаги", "bullet"),
    "question": Target(ACTIVE, "Открытые вопросы к команде", "bullet"),
    "debt": Target(PROGRESS, "Технический долг", "bullet"),
    "problem": Target(PROGRESS, "Известные проблемы", "table"),
    "discrepancy": Target(PROGRESS, "Расхождения база↔код", "table"),
}


def find_section(lines: list[str], heading: str) -> tuple[int, int] | None:
    """(индекс строки заголовка, индекс конца раздела) или None.

    Конец раздела — следующий `## `-заголовок, горизонтальная линия `---`
    (подвал файла) или конец файла.
    """
    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"## {heading}":
            start = i
            break
    if start is None:
        return None
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ") or lines[j].strip() == "---":
            return start, j
    return start, len(lines)


def insert_entry(text: str, heading: str, entry: str, kind: str) -> str | None:
    """Вставляет запись в конец раздела; None — раздел не найден.

    bullet — после последней непустой строки раздела;
    table — после последней строки таблицы (`|...`) раздела.
    """
    lines = text.splitlines()
    section = find_section(lines, heading)
    if section is None:
        return None
    start, end = section

    insert_at = None
    for i in range(end - 1, start, -1):
        line = lines[i]
        if kind == "table" and line.lstrip().startswith("|"):
            insert_at = i + 1
            break
        if kind == "bullet" and line.strip():
            insert_at = i + 1
            break
    if insert_at is None:
        if kind == "table":
            return None  # таблица раздела не найдена — структура файла изменена
        insert_at = start + 1

    lines.insert(insert_at, entry)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def detect_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if (Path.cwd() / "memory-bank").is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="корень репозитория")
    parser.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                        help="дата записи (по умолчанию — сегодня)")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("focus", "done", "next", "question", "debt"):
        p = sub.add_parser(name, help=f"запись в раздел «{TARGETS[name].heading}»")
        p.add_argument("text")

    p = sub.add_parser("problem", help="строка в таблицу «Известные проблемы»")
    p.add_argument("text")
    p.add_argument("--impact", default="—")
    p.add_argument("--workaround", default="—")
    p.add_argument("--issue", default="—")

    p = sub.add_parser("discrepancy", help="строка в таблицу «Расхождения база↔код»")
    p.add_argument("doc", help="путь документа относительно memory-bank/, напр. architecture/overview.md")
    p.add_argument("text", help="что именно расходится")
    p.add_argument("--by", default="agent", help="кто заметил (по умолчанию: agent)")
    return parser


def format_entry(args: argparse.Namespace, entry_date: str) -> str:
    if args.command == "problem":
        return f"| {entry_date} — {args.text} | {args.impact} | {args.workaround} | {args.issue} |"
    if args.command == "discrepancy":
        return f"| {args.doc} | {args.text} | {args.by} | {entry_date} |"
    return f"- {entry_date} — {args.text}"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_arg_parser().parse_args(argv)
    entry_date = args.date or date.today().isoformat()
    try:
        date.fromisoformat(entry_date)
    except ValueError:
        print(f"mb_log: некорректная дата {entry_date!r}, ожидается YYYY-MM-DD", file=sys.stderr)
        return 2

    target = TARGETS[args.command]
    path = detect_root(args.root) / target.file
    if not path.is_file():
        print(f"mb_log: не найден {target.file}", file=sys.stderr)
        return 1

    text = mb_lib.load(path)
    updated = insert_entry(text, target.heading, format_entry(args, entry_date), target.kind)
    if updated is None:
        print(f"mb_log: в {target.file} нет раздела «{target.heading}» "
              f"(структура файла изменена — поправьте маппинг в scripts/mb_log.py)", file=sys.stderr)
        return 1

    # entry_date датирует саму запись; frontmatter updated — всегда сегодня
    # (иначе --date в прошлом откатил бы updated и вызвал ложное MB050).
    touched = touch(updated, date.today())
    mb_lib.save(path, touched if touched is not None else updated)
    print(f"mb_log: записано в {target.file} → «{target.heading}»")

    _, body = split_document(touched or updated)
    body_lines = len(body.splitlines())
    if body_lines > BODY_WARN_LINES:
        print(f"mb_log: внимание — тело {target.file} уже {body_lines} строк "
              f"(> {BODY_WARN_LINES}): пора вычищать отработанное (_meta/lifecycle.md)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
