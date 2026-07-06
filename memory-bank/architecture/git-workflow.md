---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: ""
---

# Git workflow

Ветки, коммиты и PR в meta-bot-core. Ограничения для агентов (не коммитить
без явной просьбы) — [AGENTS.md](../../AGENTS.md); процессы под тип задачи —
[../workflows/new-feature.md](../workflows/new-feature.md) и соседние файлы.

## Модель веток

**Trunk-based.** `main` всегда релизопригоден: собирается, проходит все проверки
и в любой момент годен для выката. Работа ведётся в короткоживущих ветках
(ориентир — < 3 дней) от свежего `main`; слияние — только через PR.
Прямые пуши в `main` запрещены (branch protection). Долгих параллельных
release-веток нет — как из `main` получается релиз, описано в
[../ops/releases.md](../ops/releases.md).

## Именование веток

Формат: `<тип>/<задача>-<краткое-описание>`;
типы: `feature` | `fix` | `refactor` | `hotfix` | `chore`.

Примеры: `feature/MBC-142-max-webhook-gateway`,
`fix/MBC-155-session-fsm-reset`, `refactor/MBC-160-platform-factory`.
Префикс номера задачи (`MBC-`) — дефолт; точный формат под трекер команды
уточнить у команды.

## Коммиты

- Формат сообщения: **Conventional Commits** — `тип(область): описание`.
  Типы: `feat` | `fix` | `refactor` | `chore` | `docs` | `test`.
  Допустимые области соответствуют слоям и контекстам проекта:
  `domain` | `application` | `infra` | `platforms` | `presentation` |
  `miniapp` | `kb` (правки `memory-bank/`).
- Примеры:
  - `feat(domain): enforce Bot.publish token+flow invariant (BR-001)`;
  - `feat(platforms): add MaxBotAdapter callback answering`;
  - `fix(application): idempotent ProcessUpdateUseCase on webhook retry`;
  - `docs(kb): update git-workflow after branch-model change`.
- Коммит атомарен: одна логическая правка; проект собирается, тесты проходят.
  Правку `src/` сопровождай синхронной правкой затронутых документов
  `memory-bank/` в том же PR (см. [AGENTS.md](../../AGENTS.md)).
- **Авторство — только человек.** В сообщениях коммитов запрещены AI-трейлеры
  и любая атрибуция инструментов: `Co-Authored-By: Claude ...`,
  `Generated with ...` и аналогичные. Автор и коммиттер — человек, ведущий работу.

## Pull Request

- Размер: ориентир — до ~400 изменённых строк; больше — делите на цепочку PR.
- Описание PR: что и зачем; ссылка на задачу и ADR (если решение оформлялось,
  см. [../decisions/README.md](../decisions/README.md)); как проверялось.
  Правки `memory-bank/` упоминаются отдельно
  ([governance](../_meta/governance.md)).
- Обязательные проверки (все зелёные в CI до мержа):
  - [ ] `ruff format` и `ruff check` (форматирование и линт), `mypy` (strict) —
        [code-style.md](code-style.md);
  - [ ] арх-линтер: `lint-imports` (import-linter, контракт
        [`.importlinter`](../../.importlinter)) в CI-джобе `arch-lint`
        ([../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)) —
        границы слоёв, см. [overview.md](overview.md); красный `lint-imports` =
        закрытый мерж, протечка чинится разворотом зависимости, а не заглушкой
        ([.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md));
  - [ ] тесты по [testing-strategy.md](testing-strategy.md);
  - [ ] валидатор базы знаний, если задет `memory-bank/`
        (`python scripts/validate_memory_bank.py`; в CI —
        [../../.github/workflows/validate-memory-bank.yml](../../.github/workflows/validate-memory-bank.yml)).
- Ревью: минимум 1 апрув; для изменений в `domain/` и архитектуре — 2 апрува
  (точный порог уточнить у команды). Для изменений с внешним вводом, auth
  или ПДн — дополнительно чек-лист из [security.md](security.md);
  правки `memory-bank/` (кроме `current/`) — апрув владельца раздела
  ([governance](../_meta/governance.md)).

## Кто и как мержит

- Мержит автор после апрувов и зелёного CI (переход на merge queue —
  уточнить у команды).
- Способ слияния: `squash` — единственный включённый в настройках репозитория,
  чтобы `main` оставался линейным (подтвердить у команды).
- Прямые пуши в `main` запрещены (branch protection).
- Срочные исправления в проде — по процессу [../workflows/hotfix.md](../workflows/hotfix.md).
