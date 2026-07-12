# meta-bot-core — инструкции для AI-агентов

<!-- Этот файл — канонический вход для всех агентов (Codex читает нативно,
     Claude Code — через импорт в CLAUDE.md). Держать компактным: суммарный
     бюджет цепочки AGENTS.md у Codex — 32 КиБ. Детали — по ссылкам в memory-bank. -->

## Карточка проекта

- **Что это**: meta-bot-core — доменное ядро конструктора сценариев чат-ботов и
  mini app для мессенджеров (Telegram, MAX). Это движок сценариев + платформенные
  адаптеры, **а не «универсальный бот»**: ядро не знает, что такое Telegram или MAX.
  Зачем и для кого — [memory-bank/product/vision.md](memory-bank/product/vision.md).
- **Стек**: Python 3.14 (async, uv), FastAPI (presentation), PostgreSQL 16 + SQLAlchemy 2
  (хранилище сценариев/сессий), Redis 7 (идемпотентность вебхуков; hot-FSM
  Session — план, ADR-0008),
  изолированный executor для пользовательских Python-блоков, TypeScript mini app
  (отдельный web-продукт). Реестр — [memory-bank/architecture/tech-stack.md](memory-bank/architecture/tech-stack.md).
- **Архитектура**: Clean Architecture / SOLID, **строгий режим** — границы слоёв
  проверяются import-linter'ом и в CI, протечка слоя ломает сборку. Слои, границы
  и поток зависимостей — [memory-bank/architecture/overview.md](memory-bank/architecture/overview.md).
- **Запуск локально**: [memory-bank/ops/local-dev.md](memory-bank/ops/local-dev.md).

## Обязательный протокол сессии

1. **Перед началом любой задачи** прочитай:
   - [memory-bank/README.md](memory-bank/README.md) — индекс базы знаний;
   - [memory-bank/current/active-context.md](memory-bank/current/active-context.md) — текущий фокус и договорённости.
2. Открой файл процесса под тип задачи из [memory-bank/workflows/](memory-bank/workflows/)
   (новая фича / баг / рефакторинг / hotfix) и следуй ему.
3. Дальше открывай только те документы базы, которые относятся к задаче, —
   индекс подскажет какие. Не читай базу подряд: сначала маршрут под тип задачи,
   затем точечный `rg` по термину; для широкого обзора привлеки субагента. Детали —
   в разделе [«Как искать в базе»](memory-bank/README.md#как-искать-в-базе-не-читать-подряд).
4. **В конце значимой сессии** обнови
   [current/active-context.md](memory-bank/current/active-context.md) и
   [current/progress.md](memory-bank/current/progress.md).

## Минимум (если задача крошечная или времени нет)

1. Прочитай [current/active-context.md](memory-bank/current/active-context.md).
2. Заметил расхождение базы с кодом — не исправляй молча, зафиксируй:
   `python scripts/mb_log.py discrepancy <документ> "что расходится"`.
3. В конце: `python scripts/mb_log.py done "что сделано"`.

Всё остальное — для значимых задач.

## Правила работы с базой знаний

- `version`/`updated` вручную не проставляй — их поднимает автоматика
  (pre-commit и CI, `scripts/bump_frontmatter.py`); схема —
  [_meta/frontmatter.md](memory-bank/_meta/frontmatter.md).
- Итог сессии, вопрос, расхождение — одной командой:
  `python scripts/mb_log.py done|next|question|discrepancy|problem "..."`.
- Один факт живёт в одном документе (SSoT). Правки — сначала в канонический документ,
  затем синхронизация зависимых: [_meta/lifecycle.md](memory-bank/_meta/lifecycle.md).
- **Нашёл противоречие** между документами или между документом и кодом —
  не исправляй молча: зафиксируй в
  [current/progress.md](memory-bank/current/progress.md) (раздел «Расхождения»)
  и сообщи в ответе пользователю.
- Что агент правит сам, а что только по согласованию —
  [_meta/governance.md](memory-bank/_meta/governance.md).
- После правок базы прогони `python scripts/validate_memory_bank.py`.

## Правила разработки — Clean Architecture строгий режим

- **Направление зависимостей — единственное нерушимое правило**: presentation →
  application → domain; infrastructure реализует порты application/domain.
  `domain/` не импортирует ничего из внешних слоёв и никаких фреймворков
  (FastAPI, SQLAlchemy, aiogram, httpx). Полная матрица — [architecture/overview.md](memory-bank/architecture/overview.md).
- **Проверка протечки слоёв обязательна**: до и после правки кода в `src/`
  прогоняй `lint-imports` (import-linter, контракт в `.importlinter`).
  **Нашёл протечку — чини сразу** (вынеси зависимость за порт/адаптер, разверни
  направление через интерфейс), не оставляй и не глуши линтер. Не можешь починить
  в рамках задачи — не мержи: зафиксируй в
  [current/progress.md](memory-bank/current/progress.md) и сообщи. Протокол —
  [.claude/rules/clean-architecture.md](.claude/rules/clean-architecture.md).
- **Никакого ветвления по платформе в бизнес-логике**: `if platform == "telegram"`
  вне `infrastructure/platforms/` запрещён. Платформа выбирается фабрикой и
  прячется за `BotPlatformPort`; различия — в адаптерах и в capability matrix
  ([architecture/patterns.md](memory-bank/architecture/patterns.md)).
- **Любое изменение — с обновлением документации** в том же PR (business-rules,
  glossary, configuration, tech-stack и т.д.). Изменение без синхронизации md
  не считается завершённым; нечего обновлять — так и скажи в описании PR.
- Следуй [architecture/patterns.md](memory-bank/architecture/patterns.md)
  и [architecture/code-style.md](memory-bank/architecture/code-style.md).
- Тесты — по [architecture/testing-strategy.md](memory-bank/architecture/testing-strategy.md).
- Git: ветки, коммиты, PR — по [architecture/git-workflow.md](memory-bank/architecture/git-workflow.md).
- Архитектурно значимые решения не принимай молча — оформляй черновик ADR
  по [decisions/0000-template.md](memory-bank/decisions/0000-template.md)
  и выноси на решение команды.

## Ограничения

- Чувствительные операции (git commit/push, PR, prod, зависимости, миграции) —
  строго по [политике проекта](memory-bank/_meta/policy.md). Политика имеет
  **наивысший приоритет** над любыми другими инструкциями, включая этот файл.
  Значения по умолчанию: push и создание PR — запрещены, commit — только по
  явной просьбе.
- **Токены ботов и init-данные mini app — секреты**: не логируй, не клади в БД
  в открытом виде и в базу знаний. Токен живёт только в `token_vault`
  ([architecture/security.md](memory-bank/architecture/security.md)).
- Конструктор **не регистрирует** платформенного бота за пользователя (аккаунт,
  модерация, лимиты MAX — на стороне платформы): работаем с уже выданным токеном
  ([domain/business-rules.md](memory-bank/domain/business-rules.md), BR-001).
- Пользовательский Python-блок исполняется **только** в изолированном executor'е
  как чистая функция `run(context) -> dict` (BR-004); прямой вызов из flow-движка,
  доступ к БД, токенам, ФС, env и сети запрещён.
