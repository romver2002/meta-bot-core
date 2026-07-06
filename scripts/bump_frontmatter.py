#!/usr/bin/env python3
"""Авто-bump `version`/`updated` для изменённых документов memory-bank.

Снимает с людей и агентов механику версионирования: если ТЕЛО документа
изменилось относительно базовой ревизии, а `version`/`updated` — нет,
скрипт поднимает их сам. Идемпотентен: уже поднятые поля не трогает.

Режимы:
  pre-commit (по умолчанию)  застейдженные файлы против HEAD; починенные
                             файлы снова добавляются в индекс.
                             Включение: git config core.hooksPath scripts/git-hooks
  --base REF                 рабочая копия против merge-base с REF; чинит файлы.
  --base REF --check         только проверка (CI-рубеж): код выхода 1 при нарушениях.

Ограничение pre-commit-режима: при частичном стейджинге (git add -p) починка
применяется к рабочему файлу и стейджит его целиком.

Коды выхода: 0 — чисто/починено; 1 — нарушения в --check; 2 — git недоступен.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mb_lib import bump_minor, get_scalar, set_scalar, split_document  # noqa: E402


def run_git(args: list[str], cwd: Path) -> str | None:
    """stdout команды git или None при любой ошибке."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def file_at_ref(ref: str, rel: str, cwd: Path) -> str | None:
    """Содержимое файла в ревизии (`ref:путь`); None, если файла там нет."""
    return run_git(["show", f"{ref}:{rel}"], cwd)


def changed_bank_files(cwd: Path, base: str | None) -> list[str]:
    """Изменённые memory-bank/**/*.md: staged против HEAD либо HEAD против base."""
    if base is None:
        args = ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "--", "memory-bank"]
    else:
        args = ["diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD", "--", "memory-bank"]
    output = run_git(args, cwd)
    if output is None:
        return []
    return [line for line in output.splitlines() if line.endswith(".md")]


def stale_fields(old_text: str, new_text: str) -> list[str]:
    """Какие поля не подняты при изменившемся теле: [], ['version'], ['updated'], оба.

    Пустой список — bump не нужен (тело не менялось, поля уже подняты
    или документ вне схемы — им займётся валидатор).
    """
    old_fm, old_body = split_document(old_text)
    new_fm, new_body = split_document(new_text)
    if new_fm is None or old_fm is None or old_body == new_body:
        return []
    stale = []
    if get_scalar(new_fm, "version") == get_scalar(old_fm, "version"):
        stale.append("version")
    if get_scalar(new_fm, "updated") == get_scalar(old_fm, "updated"):
        stale.append("updated")
    return stale


def fix_text(text: str, fields: list[str], today: date) -> str:
    """Поднимает только непроставленные поля (уважает ручной bump другого поля)."""
    fm_block, body = split_document(text)
    assert fm_block is not None  # гарантировано stale_fields
    if "version" in fields:
        fm_block = set_scalar(fm_block, "version", f'"{bump_minor(get_scalar(fm_block, "version"))}"')
    if "updated" in fields:
        fm_block = set_scalar(fm_block, "updated", today.isoformat())
    return fm_block + body


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=None, metavar="REF",
                        help="базовая ревизия; без неё — pre-commit-режим (staged против HEAD)")
    parser.add_argument("--check", action="store_true",
                        help="не чинить, а проверять (для CI); требует --base")
    parser.add_argument("--root", type=Path, default=None, help="корень репозитория")
    args = parser.parse_args(argv)

    if args.check and args.base is None:
        parser.error("--check требует --base")

    cwd = args.root or Path.cwd()
    toplevel = run_git(["rev-parse", "--show-toplevel"], cwd)
    if toplevel is None:
        print("bump_frontmatter: git-репозиторий не найден", file=sys.stderr)
        return 2
    root = Path(toplevel.strip())

    old_ref = args.base if args.base is not None else "HEAD"
    violations: list[str] = []

    for rel in changed_bank_files(root, args.base):
        old_text = file_at_ref(old_ref, rel, root)
        if old_text is None:
            continue  # новый файл: version/updated ставит автор, схему проверит валидатор
        if args.base is None:
            new_text = file_at_ref("", rel, root)  # ":путь" — содержимое индекса (stage 0)
        else:
            try:
                new_text = (root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        if new_text is None:
            continue

        fields = stale_fields(old_text, new_text)
        if not fields:
            continue
        if args.check:
            if not rel.startswith("memory-bank/current/"):
                violations.append(rel)
            continue

        disk_text = (root / rel).read_text(encoding="utf-8")
        (root / rel).write_text(fix_text(disk_text, fields, date.today()), encoding="utf-8")
        if args.base is None:
            run_git(["add", rel], root)
        print(f"bump_frontmatter: {rel} → {', '.join(fields)} обновлены")

    if violations:
        for rel in violations:
            print(f"ОШИБКА {rel}: тело изменено, а version/updated — нет. "
                  f"Локальная починка: python scripts/bump_frontmatter.py --base {args.base}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
