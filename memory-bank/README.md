---
status: active
version: "1.3"
updated: 2026-07-08
verified_commit: ""
owner: "teamlead"
---

# База знаний meta-bot-core — индекс

Вход в базу знаний для агентов и людей. Читается первым в каждой сессии.
Дальше открывай только разделы, относящиеся к задаче.

## Что читать под задачу

| Задача | Обязательно | По необходимости |
|---|---|---|
| Новая фича | [workflows/new-feature.md](workflows/new-feature.md), [current/active-context.md](current/active-context.md) | domain/, architecture/, product/roadmap.md |
| Баг | [workflows/bug-fix.md](workflows/bug-fix.md), [current/progress.md](current/progress.md) | ops/runbooks/, architecture/overview.md |
| Рефакторинг | [workflows/refactoring.md](workflows/refactoring.md), [architecture/patterns.md](architecture/patterns.md) | decisions/, architecture/overview.md |
| Hotfix / инцидент | [workflows/hotfix.md](workflows/hotfix.md), [ops/runbooks/README.md](ops/runbooks/README.md) | ops/environments.md, ops/observability.md |
| Вопрос «почему так устроено» | [decisions/README.md](decisions/README.md) | architecture/overview.md |
| Работа с самой базой | [_meta/lifecycle.md](_meta/lifecycle.md) | _meta/governance.md, _meta/frontmatter.md |

## Карта разделов

### _meta/ — правила самой базы
- [policy.md](_meta/policy.md) — политика прав агентов: git, prod, зависимости (наивысший приоритет)
- [governance.md](_meta/governance.md) — кто владеет какими фактами; что агент правит сам, а что нет
- [frontmatter.md](_meta/frontmatter.md) — схема метаданных документов (версия/дата/статус)
- [lifecycle.md](_meta/lifecycle.md) — жизненный цикл документов: обновление, синхронизация, архивирование

### product/ — продукт (стабильный, владелец: продукт/тимлид)
- [vision.md](product/vision.md) — зачем продукт существует, для кого, ценность
- [roadmap.md](product/roadmap.md) — направления и приоритеты
- [metrics.md](product/metrics.md) — какие метрики считаем успехом

### domain/ — предметная область (стабильный)
- [glossary.md](domain/glossary.md) — глоссарий: термины и их значение в коде
- [domain-model.md](domain/domain-model.md) — сущности, агрегаты, инварианты
- [flow-blocks.md](domain/flow-blocks.md) — каталог блоков сценария (типы узлов и триггеров)
- [business-rules.md](domain/business-rules.md) — бизнес-правила и их источники
- [bounded-contexts.md](domain/bounded-contexts.md) — контексты и их интеграция

### architecture/ — инженерия (стабильный)
- [overview.md](architecture/overview.md) — слои Clean Architecture, границы, поток зависимостей
- [platform-reference.md](architecture/platform-reference.md) — проверенный справочник Telegram Bot API и MAX Bot API (хосты, webhook, mini app)
- [tech-stack.md](architecture/tech-stack.md) — стек и версии, что можно/нельзя добавлять
- [patterns.md](architecture/patterns.md) — принятые паттерны и анти-паттерны
- [testing-strategy.md](architecture/testing-strategy.md) — пирамида тестов, что покрываем обязательно
- [code-style.md](architecture/code-style.md) — стиль, соглашения об именовании
- [security.md](architecture/security.md) — требования безопасности, работа с секретами
- [git-workflow.md](architecture/git-workflow.md) — ветки, коммиты, PR, релизные ветки

### ops/ — эксплуатация (стабильный)
- [local-dev.md](ops/local-dev.md) — локальный запуск с нуля
- [environments.md](ops/environments.md) — окружения (dev/stage/prod), доступы, отличия
- [configuration.md](ops/configuration.md) — конфигурация и переменные окружения
- [releases.md](ops/releases.md) — как релизим, версионирование, откаты
- [observability.md](ops/observability.md) — логи, метрики, алерты, где смотреть
- [runbooks/](ops/runbooks/README.md) — инструкции по инцидентам
- [runbooks/incident-template.md](ops/runbooks/incident-template.md) — шаблон ранбука

### decisions/ — архитектурные решения (append-only)
- [README.md](decisions/README.md) — реестр ADR и правила ведения
- [0000-template.md](decisions/0000-template.md) — шаблон ADR
- [0001-clean-architecture.md](decisions/0001-clean-architecture.md) — Clean Architecture + SOLID, строгий режим (accepted)
- [0002-domain-core-and-adapters.md](decisions/0002-domain-core-and-adapters.md) — доменное ядро + платформенные адаптеры (accepted)
- [0003-flow-engine-blocks-and-sandbox.md](decisions/0003-flow-engine-blocks-and-sandbox.md) — движок на блоках + изолированные Python-блоки (proposed)
- [0004-webhook-platform-integration.md](decisions/0004-webhook-platform-integration.md) — приём обновлений через webhook (proposed)
- [0005-capability-matrix.md](decisions/0005-capability-matrix.md) — матрица возможностей платформ (proposed)
- [0006-mini-app-as-web-product.md](decisions/0006-mini-app-as-web-product.md) — mini app как отдельный web-продукт (proposed)
- [0007-visual-flow-editor.md](decisions/0007-visual-flow-editor.md) — визуальный редактор сценариев: React + React Flow (proposed)
- [0008-persistence-model.md](decisions/0008-persistence-model.md) — модель хранения: версии Flow в JSONB, Session в PG+Redis (proposed)
- [0009-max-adapter-thin-client.md](decisions/0009-max-adapter-thin-client.md) — MaxBotAdapter: тонкий httpx-клиент вместо SDK maxapi (proposed)

### workflows/ — процессы под тип задачи (стабильный)
- [new-feature.md](workflows/new-feature.md) — процесс новой фичи (включая связку со spec-kit)
- [bug-fix.md](workflows/bug-fix.md) — процесс исправления бага
- [refactoring.md](workflows/refactoring.md) — процесс рефакторинга
- [hotfix.md](workflows/hotfix.md) — срочное исправление в продакшене

### current/ — живое состояние (обновляется каждую значимую сессию)
- [active-context.md](current/active-context.md) — текущий фокус, последние договорённости
- [progress.md](current/progress.md) — статус, известные проблемы, расхождения база↔код

## Договорённости

- Схема метаданных и версионирования — [_meta/frontmatter.md](_meta/frontmatter.md);
  правила обновления — [_meta/lifecycle.md](_meta/lifecycle.md).
- Добавил/удалил/переименовал документ → обнови этот индекс в том же PR.
- Валидация: `python scripts/validate_memory_bank.py` (гоняется и в CI).
