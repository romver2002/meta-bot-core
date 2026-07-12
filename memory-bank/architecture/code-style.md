---
status: active
version: "1.1"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Стиль кода

Соглашения meta-bot-core поверх автоматики. Принцип: всё, что может проверить
машина, проверяет машина — здесь только то, что она не поймает. Стек, к которому
относятся инструменты, — [tech-stack.md](tech-stack.md); границы слоёв, которые
стиль обязан поддерживать, — [overview.md](overview.md).

## Инструменты

Форматирование и статические проверки — обязательны локально (до и после правки
`src/`), в pre-commit и в CI. Форматирование в ревью не обсуждается: спор решает
конфиг, а не человек.

| Инструмент | Роль | Конфиг |
|---|---|---|
| ruff format | форматирование — в ревью не обсуждается | `pyproject.toml` |
| ruff (lint) | стиль и типовые ошибки (замена flake8/isort) | `pyproject.toml` |
| mypy (strict) | статическая типизация, режим `strict` | `pyproject.toml` |
| import-linter (арх-линтер) | границы слоёв — см. [overview.md](overview.md) | [`.importlinter`](../../.importlinter) |

Запуск: локально — `ruff format`, `ruff check`, `mypy` и `lint-imports`; те же
проверки в pre-commit и в CI. Границы слоёв проверяет отдельная CI-джоба
`arch-lint` ([../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)):
красный `lint-imports` = красная сборка, мерж закрыт. Протокол исправления
протечки слоя — [.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md).

## Именование

- Источник имён — [глоссарий](../domain/glossary.md): сущности, статусы и операции
  в коде называются так же, как там (Ubiquitous Language). Термина нет в глоссарии —
  сначала добавь его туда, потом используй в коде.
- Один термин — одно имя: не `Bot` в одном модуле и `Chatbot` в другом; не
  `Flow` и `Scenario` вперемешку.
- Use case — глагол + существительное + `UseCase`: `CreateBotUseCase`,
  `PublishBotUseCase`, `ProcessUpdateUseCase`, `AttachMiniAppUseCase`,
  `AuthenticateMiniAppUseCase`, `SubmitMiniAppResultUseCase`.
- Порт и реализация:
  - порт-репозиторий → реализация с префиксом технологии: `FlowRepository` →
    `PgFlowRepository`, `SessionRepository` → `PgSessionRepository`;
  - платформенный порт → адаптер с суффиксом платформы: `BotPlatformPort` →
    `TelegramBotAdapter`, `MaxBotAdapter` (см. [глоссарий](../domain/glossary.md)).
- Запрещены имена-заглушки: `Manager`, `Helper`, `Util`, `Impl`, `data2` — они
  прячут отсутствие ответственности; см. анти-паттерны в [patterns.md](patterns.md).
- Регистры (Python): модули и функции — `snake_case`, классы — `PascalCase`,
  константы — `UPPER_SNAKE_CASE`, имена файлов — `snake_case`
  (`process_update.py`, `bot_platform.py`).

## Структура модулей

Внутри каждого слоя код режется по фичам/агрегатам, а не по «типам» файлов.
Общий код выносится в `shared/` только после третьего использования, а не «на
вырост».

Ориентировочно (канон дерева — [overview.md](overview.md)):

```
application/
  use_cases/          process_update.py  create_bot.py  publish_bot.py  …
  ports/              bot_platform.py  flow_repository.py  session_repository.py  …
infrastructure/
  platforms/
    telegram/         adapter.py  mapper.py  webhook.py  mini_app_auth.py
    max/              adapter.py  mapper.py  webhook.py  mini_app_auth.py
```

- Ветвление по платформе (`if platform == "telegram"`) вне
  `infrastructure/platforms/` запрещено (BR-005): платформу выбирает
  `PlatformFactory`, различия скрыты за `BotPlatformPort` и в `CapabilityMatrix`.
  Ловится ревью и арх-линтером — см. [overview.md](overview.md), [patterns.md](patterns.md).

## Комментарии и докстрины

- Комментарий объясняет «почему», а не «что»: «что» должно читаться из имён и структуры.
- Реализуешь бизнес-правило — ссылайся на его идентификатор `BR-XXX` в
  [business-rules.md](../domain/business-rules.md), чтобы код и база знаний сходились
  (напр. `# BR-001: публикация только с валидным токеном и непустым Flow`).
- TODO в коде — только адресный: `TODO(#123): ...`. Безадресный TODO не проходит ревью.
- Публичные порты (`application/ports/`) и use cases — с докстрингом: контракт,
  выбрасываемые доменные ошибки.
- Закомментированный код не хранится — удаляется, история остаётся в git.

## Чек-лист самопроверки перед PR

- [ ] `ruff format`, `ruff check`, `mypy` (strict) и `lint-imports` зелёные локально.
- [ ] Имена новых сущностей, портов и use case сверены с [глоссарием](../domain/glossary.md).
- [ ] Нет `if platform == …` вне `infrastructure/platforms/` (BR-005).
- [ ] Нет безадресных TODO и закомментированного кода.
