#!/usr/bin/env python3
"""Очистка локальных регенерируемых артефактов — одной командой.

Инструменты (pytest, mypy, ruff, import-linter, uv, hatchling) складывают кеши
и сборочный мусор в корень проекта. В git/Docker они не попадают (.gitignore,
.dockerignore), но засоряют рабочее дерево. Скрипт удаляет их безопасно:

  python scripts/clean.py            # кеши сборки/тестов/линтеров + __pycache__
  python scripts/clean.py --deep     # плюс координационный кеш ruflo (.swarm и т.п.)
  python scripts/clean.py --dry-run  # только показать, что было бы удалено

НИКОГДА не трогает рабочее окружение и секреты: .venv/, node_modules/, .env.
Всё удаляемое пересоздаётся инструментами при следующем прогоне.

Коды выхода: 0 — успех; 2 — некорректный вызов.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

# Кириллица в выводе не должна ломаться в cp1251-консоли Windows (PowerShell/cmd).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# Точечные пути в корне (каталоги и файлы) — стандартные артефакты инструментов.
DEFAULT_PATHS = (
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".import_linter_cache",
    ".uv-cache",
    ".coverage",
    "htmlcov",
    "dist",
    "frontend/constructor/dist",
)

# Координационный кеш ruflo/claude-flow — «не источник истины» (см. .gitignore).
# Убирается только с --deep, чтобы случайно не стереть память активного роя.
DEEP_PATHS = (
    ".swarm",
    ".claude-flow",
    ".hive-mind",
    "ruvector.db",
)

# Рекурсивные шаблоны — мусор, разбросанный по дереву пакетов.
GLOB_PATTERNS = ("**/__pycache__", "**/*.egg-info", "**/*.pyc")

# Каталоги, внутрь которых не спускаемся при обходе (и никогда не удаляем).
PRUNE_DIRS = {".git", ".venv", "venv", "node_modules", "Templater"}


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def _size_of(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for current, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(current) / name).stat().st_size
            except OSError:
                pass
    return total


def _on_rm_error(func, path, _exc) -> None:  # noqa: ANN001
    """Windows держит read-only флаг (например у .git-подобных кешей) — снимаем."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _remove(path: Path, *, dry_run: bool) -> int:
    size = _size_of(path)
    rel = path.relative_to(ROOT)
    if dry_run:
        print(f"  [dry-run] {rel}  ({_human(size)})")
        return size
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, onexc=_on_rm_error)
    else:
        path.unlink(missing_ok=True)
    print(f"  removed  {rel}  ({_human(size)})")
    return size


def _iter_glob_targets() -> list[Path]:
    targets: list[Path] = []
    for pattern in GLOB_PATTERNS:
        for match in ROOT.glob(pattern):
            if any(part in PRUNE_DIRS for part in match.relative_to(ROOT).parts):
                continue
            targets.append(match)
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Очистка регенерируемых артефактов проекта.")
    parser.add_argument("--deep", action="store_true", help="также удалить координационный кеш ruflo")
    parser.add_argument("--dry-run", action="store_true", help="показать, что было бы удалено, ничего не трогая")
    args = parser.parse_args(argv)

    names = list(DEFAULT_PATHS) + (list(DEEP_PATHS) if args.deep else [])
    targets = [ROOT / name for name in names if (ROOT / name).exists()]
    targets += _iter_glob_targets()

    # Убираем вложенность: если каталог уже в списке, не удаляем отдельно его
    # содержимое (иначе двойной счёт байтов и шумные строки после rmtree).
    dirs = {t for t in targets if t.is_dir() and not t.is_symlink()}
    targets = [t for t in targets if not any(parent in dirs for parent in t.parents)]

    if not targets:
        print("Чисто — удалять нечего.")
        return 0

    freed = 0
    removed = 0
    for target in targets:
        # Страховка: никогда не удаляем рабочее окружение / секреты.
        if target.name in PRUNE_DIRS or target.name in {".env"}:
            continue
        freed += _remove(target, dry_run=args.dry_run)
        removed += 1

    verb = "было бы освобождено" if args.dry_run else "освобождено"
    print(f"\n{removed} объект(ов), {verb} ~{_human(freed)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
