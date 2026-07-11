#!/usr/bin/env python3
"""Авто-bump `version`/`updated` для изменённых документов memory-bank.

Снимает с людей и агентов механику версионирования: если ТЕЛО документа
изменилось относительно базовой ревизии, а `version`/`updated` не поднялись
(или version уехала назад), скрипт чинит их сам, поднимая version от базовой.
Идемпотентен: уже поднятые (выросшие) поля не трогает.

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
from mb_lib import (  # noqa: E402
    bump_minor, get_scalar, normalize_newlines, set_scalar, split_document, version_increased,
)


def run_git(args: list[str], cwd: Path) -> str | None:
    """stdout команды git или None при любой ошибке.

    `core.quotePath=false` заставляет git отдавать сырые UTF-8 пути,
    а не octal-escape в кавычках — иначе кириллические имена файлов
    молча выпадают из обработки.
    """
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", *args], cwd=cwd,
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def ref_exists(ref: str, cwd: Path) -> bool:
    return run_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd) is not None


def file_at_ref(ref: str, rel: str, cwd: Path) -> str | None:
    """Содержимое файла в ревизии (`ref:путь`, LF-нормализованное); None, если файла нет."""
    raw = run_git(["show", f"{ref}:{rel}"], cwd)
    return None if raw is None else normalize_newlines(raw)


def changed_bank_files(cwd: Path, base: str | None) -> list[tuple[str | None, str]]:
    """Пары (путь_в_базовой_ревизии, текущий_путь) для изменённых memory-bank/*.md.

    Для переименований (статус R) базовый путь — СТАРОЕ имя, текущий — новое,
    иначе переименование+правка обходит проверку bump. Для новых файлов (A)
    базовый путь = None. `-z` даёт NUL-разделённый машинный вывод.
    """
    if base is None:
        args = ["diff", "--cached", "--name-status", "-M", "-z", "--", "memory-bank"]
    else:
        args = ["diff", "--name-status", "-M", "-z", f"{base}..HEAD", "--", "memory-bank"]
    output = run_git(args, cwd)
    if output is None:
        return []

    tokens = output.split("\0")
    pairs: list[tuple[str | None, str]] = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        if status[0] in ("R", "C"):  # переименование/копия: старый и новый пути
            old_path, new_path = tokens[i + 1], tokens[i + 2]
            i += 3
            if new_path.endswith(".md"):
                pairs.append((old_path, new_path))
        else:  # A/M/D — один путь
            path = tokens[i + 1]
            i += 2
            if status[0] == "D" or not path.endswith(".md"):
                continue
            pairs.append((None if status[0] == "A" else path, path))
    return pairs


def stale_fields(old_text: str, new_text: str) -> list[str]:
    """Какие поля не подняты при изменившемся теле: [], ['version'], ['updated'], оба.

    `version` считается непроставленным, если новая версия НЕ выросла относительно
    базовой (равна или, по ошибке, понижена) — так ловится и забытый bump, и откат
    номера назад. Ручной мажорный/минорный подъём (new > old) уважается.
    Пустой список — bump не нужен (тело не менялось, поля уже подняты
    или документ вне схемы — им займётся валидатор).
    """
    old_fm, old_body = split_document(old_text)
    new_fm, new_body = split_document(new_text)
    if new_fm is None or old_fm is None or old_body == new_body:
        return []
    stale = []
    if not version_increased(get_scalar(old_fm, "version"), get_scalar(new_fm, "version")):
        stale.append("version")
    if get_scalar(new_fm, "updated") == get_scalar(old_fm, "updated"):
        stale.append("updated")
    return stale


def fix_text(text: str, fields: list[str], today: date, base_version: str | None = None) -> str:
    """Поднимает только непроставленные поля (уважает ручной bump другого поля).

    `base_version` — версия в базовой ревизии; version поднимается от неё, а не от
    текущего (возможно, ошибочно пониженного) значения, чтобы номер не пополз назад.
    Без base_version бампится от текущего значения (совместимость со старыми вызовами).
    """
    fm_block, body = split_document(text)
    assert fm_block is not None  # гарантировано stale_fields
    if "version" in fields:
        base = base_version if base_version is not None else get_scalar(fm_block, "version")
        fm_block = set_scalar(fm_block, "version", f'"{bump_minor(base)}"')
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

    if args.base is not None:
        if not ref_exists(args.base, root):
            print(f"bump_frontmatter: базовая ревизия {args.base!r} недостижима "
                  f"(опечатка/не сделан fetch?)", file=sys.stderr)
            return 2  # git-ошибку не путаем с «всё чисто»
        merge_base = run_git(["merge-base", args.base, "HEAD"], root)
        if merge_base is None:
            print(f"bump_frontmatter: нет общего предка с {args.base}", file=sys.stderr)
            return 2
        old_ref = merge_base.strip()  # сверяемся с точкой ветвления, как и отбор файлов
    else:
        old_ref = "HEAD"

    violations: list[str] = []
    from mb_lib import load, save  # noqa: PLC0415 — локально, чтобы не тянуть в тесты логики

    for old_rel, new_rel in changed_bank_files(root, old_ref if args.base else None):
        if old_rel is None:
            continue  # новый файл: version/updated ставит автор, схему проверит валидатор
        old_text = file_at_ref(old_ref, old_rel, root)
        if old_text is None:
            continue
        if args.base is None:
            new_text = file_at_ref("", new_rel, root)  # ":путь" — содержимое индекса (stage 0)
        else:
            try:
                new_text = load(root / new_rel)
            except (OSError, UnicodeDecodeError):
                continue
        if new_text is None:
            continue

        fields = stale_fields(old_text, new_text)
        if not fields:
            continue
        if args.check:
            if not new_rel.startswith("memory-bank/current/"):
                violations.append(new_rel)
            continue

        base_fm, _ = split_document(old_text)
        base_version = get_scalar(base_fm, "version")  # бампим от базовой версии, не назад
        save(root / new_rel, fix_text(load(root / new_rel), fields, date.today(), base_version))
        if args.base is None:
            run_git(["add", new_rel], root)
        print(f"bump_frontmatter: {new_rel} → {', '.join(fields)} обновлены")

    if violations:
        for rel in violations:
            print(f"ОШИБКА {rel}: тело изменено, а version не поднята (или понижена) / updated не обновлён. "
                  f"Локальная починка: python scripts/bump_frontmatter.py --base {args.base}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
