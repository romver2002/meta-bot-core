#!/usr/bin/env python3
"""Разовый бутстрап репозитория: включает собственные предохранители одной командой.

Чтобы не помнить `git config core.hooksPath ...` на каждом клоне. Идемпотентен,
кросс-платформенный, только стандартная библиотека.

Что делает:
  - включает git pre-commit-хук (core.hooksPath = scripts/git-hooks) — с ним
    scripts/bump_frontmatter.py поднимает version/updated на каждом коммите;
  - на unix проставляет +x на scripts/git-hooks/pre-commit;
  - прогоняет валидатор базы один раз (информативно — setup не падает от находок).

  python scripts/setup.py            включить и проверить
  python scripts/setup.py --check    только проверить (ничего не менять)

ВАЖНО: core.hooksPath — ЛОКАЛЬНЫЙ git-конфиг, он не коммитится и в чистый
CI-чекаут не попадает. Этот скрипт — локальное удобство и ранняя обратная связь;
настоящий непробиваемый рубеж — проверка `bump_frontmatter.py --check` в CI.

Коды выхода: 0 — настроено / проверка прошла; 1 — --check: хук не включён;
2 — git недоступен / не репозиторий / нет файла хука / hooksPath занят другим хуком.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

HOOKS_PATH = "scripts/git-hooks"
HOOK_FILE = "scripts/git-hooks/pre-commit"


def run_git(args: list[str], cwd: Path) -> str | None:
    """stdout команды git или None при любой ошибке (в т.ч. незаданный ключ config)."""
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def repo_root(start: Path) -> Path | None:
    top = run_git(["rev-parse", "--show-toplevel"], start)
    return Path(top.strip()) if top else None


def configured_hooks_path(root: Path) -> str | None:
    current = run_git(["config", "--local", "core.hooksPath"], root)
    return current.strip() if current is not None else None


def hook_configured(root: Path) -> bool:
    return configured_hooks_path(root) == HOOKS_PATH


def report_hooks_path_conflict(current: str) -> None:
    print(
        f"setup: core.hooksPath уже равен {current!r}; не перезаписываю чужую настройку. "
        f"Освободите её вручную или объедините хуки с {HOOKS_PATH}.",
        file=sys.stderr,
    )


def make_executable(path: Path) -> None:
    """Добавляет биты выполнения, не трогая остальные (нужно только на unix)."""
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def run_validator(root: Path) -> str | None:
    """Строка-итог валидатора базы или None, если запустить не удалось."""
    try:
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "validate_memory_bank.py")],
            cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return None
    summary = [ln for ln in result.stdout.splitlines() if ln.startswith("Проверено файлов")]
    return summary[-1] if summary else f"код выхода {result.returncode}"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="только проверить, включён ли хук (ничего не менять)")
    parser.add_argument("--root", type=Path, default=None, help="корень репозитория")
    args = parser.parse_args(argv)

    root = repo_root(args.root or Path.cwd())
    if root is None:
        print("setup: git-репозиторий не найден (запусти из клона репозитория)", file=sys.stderr)
        return 2

    current_hooks_path = configured_hooks_path(root)
    if args.check:
        if current_hooks_path == HOOKS_PATH:
            print(f"setup: pre-commit включён (core.hooksPath = {HOOKS_PATH})")
            return 0
        if current_hooks_path is not None:
            report_hooks_path_conflict(current_hooks_path)
            return 2
        print("setup: pre-commit НЕ включён — запусти: python scripts/setup.py", file=sys.stderr)
        return 1

    hook_file = root / HOOK_FILE
    if not hook_file.is_file():
        print(f"setup: не найден файл хука {HOOK_FILE} — репозиторий неполный", file=sys.stderr)
        return 2

    if current_hooks_path == HOOKS_PATH:
        print("setup: pre-commit уже включён — пропускаю")
    elif current_hooks_path is not None:
        report_hooks_path_conflict(current_hooks_path)
        return 2
    elif run_git(["config", "core.hooksPath", HOOKS_PATH], root) is None:
        print("setup: не удалось записать core.hooksPath (git недоступен?)", file=sys.stderr)
        return 2
    else:
        print(f"setup: pre-commit включён (core.hooksPath = {HOOKS_PATH})")

    if os.name != "nt":
        make_executable(hook_file)
        print(f"setup: +x на {HOOK_FILE}")

    summary = run_validator(root)
    if summary is not None:
        print(f"setup: валидатор базы — {summary}")

    print("setup: готово. version/updated теперь поднимаются автоматикой при коммите.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
