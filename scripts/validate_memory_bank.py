#!/usr/bin/env python3
"""Валидатор базы знаний (memory-bank).

Назначение: единственный механический контролёр качества базы знаний.
Запускается локально и в CI (`.github/workflows/validate-memory-bank.yml`).

Архитектура
-----------
- Загрузка: каждый документ читается с диска ровно один раз и превращается
  в `Document` (frontmatter, тело, ссылки).
- Проверки: независимые функции-правила, зарегистрированные декоратором
  `@check`. Каждая получает `Context` и возвращает находки `Finding`.
- Отчёт: текстовый или JSON (стабильный контракт, см. `render_json`).

Как добавить правило
--------------------
1. Добавьте запись в `RULES` с новым кодом MBxxx, серьёзностью и описанием.
2. Напишите функцию `check_*` с декоратором `@check`, возвращающую находки.
3. Добавьте тест в `scripts/test_validate_memory_bank.py`.

Коды выхода: 0 — чисто; 1 — есть ошибки (при --strict также предупреждения);
2 — некорректный запуск (memory-bank не найден).

Только стандартная библиотека, Python 3.10+.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from datetime import date, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Iterator

VALIDATOR_VERSION = "2.0.0"
JSON_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Модель
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


_SEVERITY_ORDER = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


@dataclasses.dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    summary: str


RULES: dict[str, Rule] = {r.id: r for r in (
    Rule("MB001", Severity.ERROR, "файл не в кодировке UTF-8"),
    Rule("MB002", Severity.ERROR, "пустой файл"),
    Rule("MB010", Severity.ERROR, "отсутствует frontmatter"),
    Rule("MB011", Severity.ERROR, "frontmatter не закрыт разделителем '---'"),
    Rule("MB012", Severity.ERROR, "недопустимое значение status"),
    Rule("MB013", Severity.ERROR, "некорректный формат version"),
    Rule("MB014", Severity.ERROR, "некорректная или отсутствующая дата updated"),
    Rule("MB015", Severity.WARNING, "updated в будущем"),
    Rule("MB016", Severity.ERROR, "недопустимое значение decision_status"),
    Rule("MB020", Severity.ERROR, "битая относительная ссылка"),
    Rule("MB021", Severity.ERROR, "ссылка выходит за пределы репозитория"),
    Rule("MB030", Severity.ERROR, "документ-сирота: недостижим из индекса"),
    Rule("MB031", Severity.ERROR, "отсутствует индекс memory-bank/README.md"),
    Rule("MB040", Severity.ERROR, "превышена максимальная глубина вложенности"),
    Rule("MB050", Severity.WARNING, "живой документ (current/) давно не обновлялся"),
    Rule("MB051", Severity.WARNING, "стабильный документ давно не обновлялся"),
    Rule("MB052", Severity.WARNING, "документ current/ длиннее мягкого лимита"),
    Rule("MB053", Severity.ERROR, "документ current/ длиннее жёсткого лимита"),
    Rule("MB060", Severity.ERROR, "AGENTS.md превышает бюджет автозагрузки Codex"),
    Rule("MB061", Severity.WARNING, "AGENTS.md приближается к бюджету автозагрузки"),
    Rule("MB062", Severity.WARNING, "AGENTS.md не найден в корне репозитория"),
    Rule("MB070", Severity.INFO, "остались маркеры TODO(template)"),
    Rule("MB071", Severity.INFO, "остались примеры-заглушки «замените своим» (выжимка: убрать при адаптации)"),
    Rule("MB080", Severity.WARNING, "отсутствует memory-bank/_meta/policy.md (политика прав агентов)"),
    Rule("MB081", Severity.ERROR, "недопустимое значение policy_* флага"),
)}


@dataclasses.dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    path: str  # repo-relative POSIX-путь; "" для находок уровня репозитория
    message: str

    def render(self) -> str:
        label = {"error": "ОШИБКА", "warning": "ВНИМАНИЕ", "info": "ИНФО"}[self.severity.value]
        location = f"{self.path}: " if self.path else ""
        return f"{self.rule} {label:<8} {location}{self.message}"


def finding(rule_id: str, path: str, message: str) -> Finding:
    rule = RULES[rule_id]
    return Finding(rule=rule.id, severity=rule.severity, path=path, message=message)


@dataclasses.dataclass(frozen=True)
class Config:
    stale_days_current: int = 14
    stale_days_stable: int = 180
    current_warn_lines: int = 80
    current_error_lines: int = 160
    agents_warn_bytes: int = 16 * 1024
    agents_error_bytes: int = 32 * 1024
    max_depth: int = 3


@dataclasses.dataclass(frozen=True)
class Frontmatter:
    data: dict[str, object]
    present: bool
    malformed: bool
    body_start: int  # индекс первой строки тела


@dataclasses.dataclass(frozen=True)
class Document:
    path: Path
    rel: str  # repo-relative POSIX-путь
    bank_rel: str  # путь внутри memory-bank
    text: str
    frontmatter: Frontmatter
    body_line_count: int
    links: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Context:
    root: Path
    bank: Path
    docs: tuple[Document, ...]
    doc_index: dict[Path, Document]  # resolved path -> Document
    agents_text: str | None
    agents_size: int
    today: date
    cfg: Config


@dataclasses.dataclass(frozen=True)
class Report:
    findings: tuple[Finding, ...]
    files_checked: int

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)


class BankNotFoundError(Exception):
    """memory-bank/ не найден в указанном корне."""


# ---------------------------------------------------------------------------
# Разбор markdown
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^\d+\.\d+$")
_FENCED_CODE_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

STATUSES = frozenset({"draft", "active", "archived"})
DECISION_STATUSES = frozenset({"proposed", "accepted", "superseded", "rejected"})
POLICY_VALUES = frozenset({"never", "ask", "always"})
POLICY_PATH = "_meta/policy.md"


def _parse_scalar(value: str) -> object:
    """Скаляр YAML-подмножества: строка с кавычками/комментарием или inline-список."""
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_scalar(part.strip()) for part in inner.split(",")]
    if len(value) >= 2 and value[0] in "\"'":
        quote = value[0]
        closing = value.find(quote, 1)
        return value[1:closing] if closing != -1 else value[1:]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def parse_frontmatter(text: str) -> Frontmatter:
    """Разбор YAML-frontmatter (осознанное подмножество).

    Поддерживаются скаляры, inline-списки и блочные списки первого уровня —
    ровно то, что допускает схема `memory-bank/_meta/frontmatter.md`.
    Вложенные отображения не поддерживаются намеренно: схема их запрещает.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return Frontmatter({}, present=False, malformed=False, body_start=0)

    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        return Frontmatter({}, present=True, malformed=True, body_start=len(lines))

    data: dict[str, object] = {}
    current_key: str | None = None
    for raw in lines[1:closing]:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key is not None:
            items = data.get(current_key)
            if not isinstance(items, list):
                items = []
                data[current_key] = items
            items.append(_parse_scalar(stripped[2:].strip()))
            continue
        if ":" in stripped and not raw.startswith((" ", "\t")):
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            value = value.strip()
            data[current_key] = _parse_scalar(value) if value else None
    return Frontmatter(data, present=True, malformed=False, body_start=closing + 1)


def extract_links(markdown: str) -> tuple[str, ...]:
    """Относительные цели ссылок; код-блоки, URI-схемы и якоря игнорируются."""
    text = _FENCED_CODE_RE.sub("", markdown)
    text = _INLINE_CODE_RE.sub("", text)
    links: list[str] = []
    for target in _LINK_RE.findall(text):
        if _URI_SCHEME_RE.match(target) or target.startswith("#"):
            continue
        target = target.split("#", 1)[0]
        if target:
            links.append(target)
    return tuple(links)


def resolve_link(source: Path, target: str, root: Path) -> Path | None:
    """Абсолютный путь цели; None, если цель выходит за пределы репозитория."""
    candidate = (source.parent / target).resolve()
    return candidate if candidate.is_relative_to(root.resolve()) else None


# ---------------------------------------------------------------------------
# Загрузка
# ---------------------------------------------------------------------------


def load_context(root: Path, cfg: Config, today: date) -> tuple[Context, list[Finding]]:
    bank = root / "memory-bank"
    if not bank.is_dir():
        raise BankNotFoundError(f"каталог memory-bank не найден в {root}")

    load_findings: list[Finding] = []
    docs: list[Document] = []
    for path in sorted(bank.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            load_findings.append(finding("MB001", rel, "файл должен быть в UTF-8"))
            continue
        if not text.strip():
            load_findings.append(finding("MB002", rel, "документ пуст"))
            continue
        fm = parse_frontmatter(text)
        docs.append(Document(
            path=path,
            rel=rel,
            bank_rel=path.relative_to(bank).as_posix(),
            text=text,
            frontmatter=fm,
            body_line_count=len(text.splitlines()) - fm.body_start,
            links=extract_links(text),
        ))

    agents_path = root / "AGENTS.md"
    agents_text: str | None = None
    agents_size = 0
    if agents_path.is_file():
        agents_size = agents_path.stat().st_size
        try:
            agents_text = agents_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            load_findings.append(finding("MB001", "AGENTS.md", "файл должен быть в UTF-8"))

    context = Context(
        root=root,
        bank=bank,
        docs=tuple(docs),
        doc_index={doc.path.resolve(): doc for doc in docs},
        agents_text=agents_text,
        agents_size=agents_size,
        today=today,
        cfg=cfg,
    )
    return context, load_findings


# ---------------------------------------------------------------------------
# Правила
# ---------------------------------------------------------------------------

CheckFn = Callable[[Context], Iterable[Finding]]
_CHECKS: list[CheckFn] = []


def check(fn: CheckFn) -> CheckFn:
    _CHECKS.append(fn)
    return fn


@check
def check_frontmatter(ctx: Context) -> Iterator[Finding]:
    """MB010–MB016: соответствие схеме memory-bank/_meta/frontmatter.md."""
    for doc in ctx.docs:
        fm = doc.frontmatter
        if not fm.present:
            yield finding("MB010", doc.rel, "добавьте frontmatter по схеме _meta/frontmatter.md")
            continue
        if fm.malformed:
            yield finding("MB011", doc.rel, "не найден закрывающий разделитель '---'")
            continue

        status = fm.data.get("status")
        if status not in STATUSES:
            yield finding("MB012", doc.rel, f"status={status!r}, допустимо: {sorted(STATUSES)}")

        version = fm.data.get("version")
        if not isinstance(version, str) or not _VERSION_RE.match(version):
            yield finding("MB013", doc.rel, f"version={version!r}, ожидается \"мажор.минор\"")

        updated = fm.data.get("updated")
        if not isinstance(updated, str):
            yield finding("MB014", doc.rel, "поле updated обязательно, формат YYYY-MM-DD")
        else:
            try:
                # Люфт в один день: bump штампует локальной датой разработчика,
                # а CI-валидатор бежит в UTC — вечерний коммит восточнее UTC иначе
                # даёт ложное «updated в будущем».
                if date.fromisoformat(updated) > ctx.today + timedelta(days=1):
                    yield finding("MB015", doc.rel, f"updated={updated} более чем на день позже сегодняшней даты")
            except ValueError:
                yield finding("MB014", doc.rel, f"updated={updated!r} не разбирается как ISO-дата")

        decision = fm.data.get("decision_status")
        if decision is not None and decision not in DECISION_STATUSES:
            yield finding("MB016", doc.rel, f"decision_status={decision!r}, допустимо: {sorted(DECISION_STATUSES)}")


@check
def check_links(ctx: Context) -> Iterator[Finding]:
    """MB020–MB021: каждая относительная ссылка указывает на существующий путь."""
    for doc in ctx.docs:
        for target in doc.links:
            resolved = resolve_link(doc.path, target, ctx.root)
            if resolved is None:
                yield finding("MB021", doc.rel, f"ссылка «{target}» уводит за пределы репозитория")
            elif not resolved.exists():
                yield finding("MB020", doc.rel, f"цель ссылки не существует: {target}")


@check
def check_reachability(ctx: Context) -> Iterator[Finding]:
    """MB030–MB031: каждый документ достижим по ссылкам из индекса базы."""
    index = (ctx.bank / "README.md").resolve()
    if index not in ctx.doc_index:
        yield finding("MB031", "memory-bank/README.md", "создайте индекс — точку входа для агентов")
        return

    reachable: set[Path] = set()
    queue: list[Path] = [index]
    while queue:
        current = queue.pop()
        if current in reachable:
            continue
        reachable.add(current)
        doc = ctx.doc_index.get(current)
        if doc is None:
            continue
        for target in doc.links:
            resolved = resolve_link(doc.path, target, ctx.root)
            if resolved is None:
                continue
            if resolved.is_dir() and (resolved / "README.md").exists():
                resolved = (resolved / "README.md").resolve()
            if resolved not in reachable:
                queue.append(resolved)

    for doc in ctx.docs:
        if doc.path.resolve() not in reachable:
            yield finding("MB030", doc.rel, "добавьте ссылку на документ в memory-bank/README.md (или удалите его)")


@check
def check_depth(ctx: Context) -> Iterator[Finding]:
    """MB040: ограничение глубины — база обязана оставаться навигируемой."""
    for doc in ctx.docs:
        depth = len(Path(doc.bank_rel).parts) - 1
        if depth > ctx.cfg.max_depth:
            yield finding("MB040", doc.rel, f"вложенность {depth} > {ctx.cfg.max_depth}")


@check
def check_freshness(ctx: Context) -> Iterator[Finding]:
    """MB050–MB051: неархивные документы не должны тихо протухать."""
    for doc in ctx.docs:
        fm = doc.frontmatter
        if fm.data.get("status") == "archived":
            continue
        updated_raw = fm.data.get("updated")
        if not isinstance(updated_raw, str):
            continue  # отсутствие/формат updated — зона MB014
        try:
            updated = date.fromisoformat(updated_raw)
        except ValueError:
            continue
        age = (ctx.today - updated).days
        if doc.bank_rel.startswith("current/"):
            if age > ctx.cfg.stale_days_current:
                yield finding("MB050", doc.rel,
                              f"не обновлялся {age} дн. (порог {ctx.cfg.stale_days_current})")
        elif age > ctx.cfg.stale_days_stable:
            yield finding("MB051", doc.rel,
                          f"не обновлялся {age} дн. — проверьте актуальность и verified_commit")


@check
def check_current_length(ctx: Context) -> Iterator[Finding]:
    """MB052–MB053: current/ читается каждую сессию и обязан оставаться коротким."""
    for doc in ctx.docs:
        if not doc.bank_rel.startswith("current/"):
            continue
        lines = doc.body_line_count
        if lines > ctx.cfg.current_error_lines:
            yield finding("MB053", doc.rel,
                          f"тело {lines} строк > {ctx.cfg.current_error_lines} — вычистить (регламент: _meta/lifecycle.md)")
        elif lines > ctx.cfg.current_warn_lines:
            yield finding("MB052", doc.rel,
                          f"тело {lines} строк > {ctx.cfg.current_warn_lines} — перенесите устоявшееся, удалите отработанное")


@check
def check_agents_budget(ctx: Context) -> Iterator[Finding]:
    """MB060–MB062: AGENTS.md загружается каждую сессию — бюджет жёсткий."""
    if ctx.agents_text is None and ctx.agents_size == 0:
        yield finding("MB062", "", "AGENTS.md — канонический вход для агентов, создайте его")
        return
    if ctx.agents_size > ctx.cfg.agents_error_bytes:
        yield finding("MB060", "AGENTS.md",
                      f"{ctx.agents_size} байт > лимита Codex {ctx.cfg.agents_error_bytes}")
    elif ctx.agents_size > ctx.cfg.agents_warn_bytes:
        yield finding("MB061", "AGENTS.md",
                      f"{ctx.agents_size} байт — выносите детали в memory-bank")


@check
def check_template_todos(ctx: Context) -> Iterator[Finding]:
    """MB070: остаток мест, требующих адаптации шаблона."""
    total = sum(doc.text.count("TODO(template)") for doc in ctx.docs)
    if ctx.agents_text:
        total += ctx.agents_text.count("TODO(template)")
    if total:
        yield finding("MB070", "", f"осталось маркеров TODO(template): {total}")


@check
def check_leftover_examples(ctx: Context) -> Iterator[Finding]:
    """MB071: примеры-заглушки, которые при адаптации проекта надо заменить/убрать.

    Выжимка: пример рядом с реальным содержимым — шум и потенциальное
    дублирование. INFO, а не WARNING, — чтобы не шуметь в самом шаблоне;
    downstream-проект видит остаток лесов и вычищает.
    """
    total = sum(doc.text.count("замените своим") for doc in ctx.docs)
    if total:
        yield finding("MB071", "", f"осталось примеров-заглушек «замените своим»: {total}")


@check
def check_policy(ctx: Context) -> Iterator[Finding]:
    """MB080–MB081: политика прав агентов существует, флаги в допустимых значениях."""
    policy = next((d for d in ctx.docs if d.bank_rel == POLICY_PATH), None)
    if policy is None:
        yield finding("MB080", "", f"создайте memory-bank/{POLICY_PATH} — права агентов не зафиксированы")
        return
    for key, value in policy.frontmatter.data.items():
        if key.startswith("policy_") and value not in POLICY_VALUES:
            yield finding("MB081", policy.rel, f"{key}={value!r}, допустимо: {sorted(POLICY_VALUES)}")


# ---------------------------------------------------------------------------
# Запуск и отчёты
# ---------------------------------------------------------------------------


def validate(root: Path, cfg: Config | None = None, today: date | None = None) -> Report:
    """Чистая точка входа: пригодна для тестов и встраивания."""
    cfg = cfg or Config()
    today = today or date.today()
    context, findings = load_context(root, cfg, today)
    for check_fn in _CHECKS:
        findings.extend(check_fn(context))
    findings.sort(key=lambda f: (_SEVERITY_ORDER[f.severity], f.path, f.rule))
    return Report(findings=tuple(findings), files_checked=len(context.docs))


def render_text(report: Report) -> str:
    lines = [f.render() for f in report.findings]
    lines.append("")
    lines.append(
        f"Проверено файлов: {report.files_checked}; "
        f"ошибок: {report.count(Severity.ERROR)}; "
        f"предупреждений: {report.count(Severity.WARNING)}"
    )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    payload = {
        "schema": JSON_SCHEMA_VERSION,
        "validator": VALIDATOR_VERSION,
        "files_checked": report.files_checked,
        "summary": {sev.value: report.count(sev) for sev in Severity},
        "findings": [
            {"rule": f.rule, "severity": f.severity.value, "path": f.path, "message": f.message}
            for f in report.findings
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_rules() -> str:
    return "\n".join(f"{r.id}  {r.severity.value:<7}  {r.summary}" for r in RULES.values())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Валидатор базы знаний (memory-bank)",
        epilog="Коды выхода: 0 — чисто; 1 — ошибки (при --strict и предупреждения); 2 — некорректный запуск.",
    )
    parser.add_argument("--root", type=Path, default=None,
                        help="корень репозитория (по умолчанию: cwd, затем каталог над scripts/)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="машиночитаемый отчёт (стабильная схема)")
    parser.add_argument("--strict", action="store_true",
                        help="предупреждения тоже дают код выхода 1")
    parser.add_argument("--ignore", action="append", default=[], metavar="MBxxx",
                        help="подавить правило (можно повторять)")
    parser.add_argument("--list-rules", action="store_true", help="показать реестр правил и выйти")
    parser.add_argument("--stale-days-current", type=int, default=Config.stale_days_current,
                        help="порог устаревания current/* в днях")
    parser.add_argument("--stale-days-stable", type=int, default=Config.stale_days_stable,
                        help="порог устаревания стабильных разделов в днях")
    return parser


def _detect_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if (Path.cwd() / "memory-bank").is_dir():
        return Path.cwd()
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = build_arg_parser().parse_args(argv)
    if args.list_rules:
        print(render_rules())
        return 0

    unknown = sorted(set(args.ignore) - RULES.keys())
    if unknown:
        print(f"Неизвестные правила в --ignore: {', '.join(unknown)}", file=sys.stderr)
        return 2

    cfg = Config(stale_days_current=args.stale_days_current,
                 stale_days_stable=args.stale_days_stable)
    try:
        report = validate(_detect_root(args.root), cfg)
    except BankNotFoundError as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 2

    if args.ignore:
        ignored = set(args.ignore)
        report = Report(
            findings=tuple(f for f in report.findings if f.rule not in ignored),
            files_checked=report.files_checked,
        )

    print(render_json(report) if args.as_json else render_text(report))

    if report.count(Severity.ERROR):
        return 1
    if args.strict and report.count(Severity.WARNING):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
