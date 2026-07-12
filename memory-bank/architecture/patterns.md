---
status: active
version: "1.1"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Паттерны и анти-паттерны

Принятые способы решения типовых задач в meta-bot-core. Слои и границы —
[overview.md](overview.md); именование — [code-style.md](code-style.md).
Термины сущностей и портов — [../domain/glossary.md](../domain/glossary.md),
правила поведения — [../domain/business-rules.md](../domain/business-rules.md).
Новый паттерн вводится через ADR ([../decisions/README.md](../decisions/README.md))
и после принятия добавляется в таблицу.

Ключевой контекст проекта: ядро конструктора не знает про Telegram и MAX. Различия
платформ живут только в `infrastructure/platforms/` — за портом `BotPlatformPort`,
в `PlatformFactory` и в `CapabilityMatrix`. Паттерны ниже подчинены этому правилу.

## Принятые паттерны

| Паттерн | Когда применять | Пример в коде |
|---|---|---|
| Ports & Adapters | всякий выход во внешний мир (платформа, БД, vault, sandbox, ФС): порт-`Protocol` в `application/ports/`, реализация в `infrastructure/` | порт `BotPlatformPort` в `src/application/ports/bot_platform.py`; адаптеры `TelegramBotAdapter` (`src/infrastructure/platforms/telegram/adapter.py`) и `MaxBotAdapter` (`src/infrastructure/platforms/max/adapter.py`) |
| Use Case / Interactor | каждый пользовательский или системный сценарий — отдельный класс в application с одним публичным методом | `ProcessUpdateUseCase`, `CreateBotUseCase`, `PublishBotUseCase`, `AttachMiniAppUseCase`, `AuthenticateMiniAppUseCase`, `SubmitMiniAppResultUseCase`, `SaveFlowDraftUseCase` и др. в `src/application/use_cases/` |
| DTO на границах | вход/выход use case и presentation; наружу процесса (HTTP, webhook, очередь) не выпускаем ORM-модели и внутренние сущности | единое событие `IncomingEvent` (`src/domain/events.py`) как платформонезависимая граница webhook→application; входные команды use case в `src/application/use_cases/` |
| Dependency Injection | все зависимости — через конструктор/параметры; сборка только в composition root | ручная сборка в `src/main.py`: создание адаптеров, репозиториев, регистрация в `PlatformFactory` (DI-контейнер — уточнить у команды, по умолчанию ручная сборка) |
| Repository | любой доступ к хранилищу сценариев и сессий: порт в application, реализация в infrastructure | `FlowRepository` (`src/application/ports/flow_repository.py`) → `PgFlowRepository` (`src/infrastructure/db/repositories.py` — модуль со всеми Pg-репозиториями); `SessionRepository` (состояние FSM `Session`) |
| PlatformFactory | выбор платформенного адаптера по `Platform` в composition root/инфраструктуре — вместо ветвления `if platform == …` | порт-`Protocol` `PlatformFactory` в `src/application/ports/bot_platform.py`; возвращает реализацию `BotPlatformPort` по `Platform` (telegram/max); реализация `RegistryPlatformFactory` — `src/infrastructure/platforms/factory.py`, наполняется адаптерами в composition root (`src/main.py`), ADR-0002 |
| CapabilityMatrix | различия платформ выражаем **данными**, а не кодом: что доступно (текст, кнопки, mini app, платежи, авторизация) на каждой платформе | класс `CapabilityMatrix` — `src/domain/capabilities.py`, данные v1 — `ENGINE_V1_CAPABILITIES` (`src/infrastructure/platforms/capabilities_v1.py`); используется в `Flow.validate_for_publication` при публикации, BR-006, [ADR-0005](../decisions/0005-capability-matrix.md) |
| CodeExecutorPort | изоляция пользовательских Python-блоков: движок не вызывает код напрямую, а идёт через порт в песочницу | порт `CodeExecutorPort` (`src/application/ports/code_executor.py`); реализация-песочница `src/infrastructure/code_executor/` — план, пока не реализована (ADR-0003); контракт блока `run(context) -> dict`, BR-004, [ADR-0003](../decisions/0003-flow-engine-blocks-and-sandbox.md) |

Пример: `ProcessUpdateUseCase` (`src/application/use_cases/process_update.py`)
получает через конструктор порты `BotRepository`, `FlowRepository`,
`SessionRepository`, `TokenVaultPort`, `PlatformFactory`, `HttpClientPort`,
`SecretResolverPort`, `NotificationTargetResolverPort` (интерфейсы из
`src/application/ports/`); `BotPlatformPort` напрямую не инжектится — конкретный
адаптер (`TelegramBotAdapter` / `MaxBotAdapter`) use case берёт вызовом
`platform_factory.for_platform(bot.platform)`, а реализация `PgFlowRepository`
лежит в `src/infrastructure/db/repositories.py`. Сам use case не импортирует
ни SDK платформ, ни SQLAlchemy — только порты и доменные типы.

## Анти-паттерны (запрещено)

| Анти-паттерн | Почему запрещён |
|---|---|
| `if platform == "telegram"/"max"` в domain или application | ветвление по платформе размазывает различия по ядру; платформу выбирает `PlatformFactory`, различия скрыты за `BotPlatformPort` и `CapabilityMatrix` (BR-005, ADR-0002/0005). Ловится import-linter + ревью |
| Бизнес-логика в адаптерах платформ или в роутах | сценарий должен жить в application/domain; адаптер только маппит `IncomingEvent`↔платформенный update и шлёт сообщения, presentation только транслирует вызовы. Иначе логика недоступна для переиспользования и unit-тестов |
| Импорт infrastructure из domain / application | ломает правило зависимостей (только внутрь); домен не знает о БД/SDK/HTTP. Ловится арх-линтером ([overview.md](overview.md), [.importlinter](../../.importlinter)) |
| Один платформенный адаптер импортит другой (`telegram` → `max`) | связывает плагины-платформы, ломает независимость; склейка — только в composition root. Проверяется контрактом `independence` в import-linter |
| Прямой вызов пользовательского Python из flow-движка | обход изоляции: доступ к БД/токенам/ФС/env/сети. Код исполняется только через `CodeExecutorPort` в песочнице как `run(context) -> dict` (BR-004) |
| ORM-модели или сущности БД в роли доменных сущностей «наружу» | схема БД начинает диктовать домен и API; смена хранилища становится невозможной. На границе — DTO, не модели SQLAlchemy |
| Service Locator, глобальные синглтоны вместо DI | скрытые зависимости, нечего подменить в тестах; всё — через конструктор, сборка в `src/main.py` |
| Обход application: presentation ходит в репозиторий/адаптер напрямую | сценарий размазывается, права и транзакции теряются |
| `*Manager` / `*Helper` / `*Util` со смешанными обязанностями | нарушает SRP; имена должны идти из глоссария ([../domain/glossary.md](../domain/glossary.md), см. [code-style.md](code-style.md)) |

## Как пользоваться

- Пишешь новый код — сначала проверь таблицу: для задачи есть принятый паттерн?
  Используй его, не изобретай параллельный.
- Задача связана с различием платформ — оно выражается **данными** в
  `CapabilityMatrix` и адаптером за `BotPlatformPort`, а не `if` по платформе.
  Границы до и после правки `src/` подтверждай `lint-imports`
  ([.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md),
  [arch-lint.yml](../../.github/workflows/arch-lint.yml)).
- Хочешь отступить от паттерна или ввести новый — не молча: черновик ADR
  ([../decisions/0000-template.md](../decisions/0000-template.md)) и обсуждение.
- Нашёл анти-паттерн в коде вне своей задачи — зафиксируй в
  [../current/progress.md](../current/progress.md), не чини мимоходом.
