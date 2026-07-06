---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: "teamlead"
---

# Архитектура meta-bot-core: обзор

Канонический документ о слоях и границах. Почему Clean Architecture и почему
**строгий режим** — ADR [0001-clean-architecture](../decisions/0001-clean-architecture.md).
Почему доменное ядро отделено от платформ — ADR
[0002-domain-core-and-adapters](../decisions/0002-domain-core-and-adapters.md).
Стек — [tech-stack.md](tech-stack.md), паттерны внутри слоёв — [patterns.md](patterns.md).

Главная мысль проекта: **ядро конструктора не знает, что такое Telegram или MAX.**
Оно оперирует абстракциями (сообщение, пользователь, кнопка, событие, сценарий,
шаг, состояние, mini app, callback). Telegram и MAX — это инфраструктура за портом.

## Слои

Четыре слоя. Корневые Python-пакеты (`src/` в `PYTHONPATH`) совпадают с именами
слоёв — это позволяет проверять границы import-linter'ом по имени пакета.

| Слой | Что содержит | Что запрещено | Пакет в коде |
|---|---|---|---|
| domain | сущности (`Bot`, `Flow`, `Node`, `Trigger`, `Button`, `MiniApp`), value objects (`Platform`, `ChatId`, `Token`), доменные события (`IncomingEvent`, `ButtonClicked`, `MiniAppOpened`), инварианты сценария, доменные ошибки | любые импорты из внешних слоёв; фреймворки, ORM, HTTP, SDK платформ, I/O | `src/domain/` |
| application | use cases (`RunFlowUseCase`, `ProcessUpdateUseCase`, `SendMessageUseCase`, `CreateBotUseCase`, `PublishBotUseCase`, `OpenMiniAppUseCase`, `ExecuteNodeUseCase`), порты (`BotPlatformPort`, `FlowRepository`, `SessionRepository`, `FileStoragePort`, `TokenVaultPort`, `CodeExecutorPort`), DTO границ | знание о конкретной БД/HTTP/SDK; условия `if platform == …`; бизнес-инварианты, дублирующие domain | `src/application/` |
| infrastructure | реализации портов: `platforms/telegram/` и `platforms/max/` (adapter, mapper, webhook, mini_app_auth), `db/` (модели SQLAlchemy, репозитории), `queue/`, `code_executor/` (sandbox), token vault | бизнес-логика; обращения к presentation; импорт одного платформенного адаптера из другого | `src/infrastructure/` |
| presentation | FastAPI-роуты: `api/admin_routes.py` (конструктор), `api/webhook_routes.py` (приём вебхуков), схемы запросов/ответов, middleware | бизнес-логика; доступ к БД/адаптерам в обход application | `src/presentation/` |

Ориентировочное дерево (канон структуры — здесь; отклонения оформляются ADR):

```
src/
  domain/         bot/entities.py  bot/value_objects.py  bot/events.py  bot/rules.py
  application/    use_cases/…  ports/bot_platform.py  ports/flow_repository.py  …
  infrastructure/ platforms/telegram/…  platforms/max/…  db/…  queue/…  code_executor/…
  presentation/   api/admin_routes.py  api/webhook_routes.py  schemas/
  main.py         # composition root
```

## Правило зависимостей

Зависимости направлены **только внутрь**: presentation → application → domain.
Infrastructure зависит от application/domain (реализует их порты), но не наоборот.

- **domain не знает ни о ком** — ни о слоях, ни о фреймворках. Проверяется как
  forbidden-контракт в `.importlinter`.
- **application знает только о domain.** Наружу ходит только через порты
  (`Protocol`-интерфейсы в `application/ports/`).
- infrastructure и presentation знают об application и domain, но **не друг о друге**
  и **не пересекаются между платформами** (`telegram` не импортит `max`) —
  склеиваются в composition root.
- Пересечение границы — только через порт и DTO, см. [patterns.md](patterns.md).
- **Платформа — это инфраструктура.** Выбор платформы делает фабрика
  (`PlatformFactory`), возвращая реализацию `BotPlatformPort`. Ветвление
  `if platform == "telegram"` вне `infrastructure/platforms/` — запрещено и
  ловится ревью + арх-линтером (см. [patterns.md](patterns.md), BR-005).

## Composition root

Единственное место, где слои склеиваются (создание зависимостей, конфигурация DI,
регистрация адаптеров платформ в `PlatformFactory`): `src/main.py`.
Только здесь допустимы импорты из всех слоёв сразу.

## Как проверяется соблюдение границ (строгий режим)

Проверка границ **обязательна и автоматизирована** — «глазами на ревью» не считается.

- Инструмент: **import-linter** (Python). Контракт — `.importlinter` в корне репозитория:
  - `layers`: `presentation` → `application` → `domain` (внешние выше внутренних);
  - `forbidden`: `domain` не импортирует `application`/`infrastructure`/`presentation`
    и внешние фреймворки (`fastapi`, `sqlalchemy`, `aiogram`, `httpx`, `redis`);
  - `independence`: `infrastructure.platforms.telegram` и
    `infrastructure.platforms.max` не импортируют друг друга.
- Запуск: `lint-imports` — локально (до и после правки `src/`), в pre-commit и в
  CI-джобе `arch-lint` ([.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)).
  Красный `lint-imports` = красная сборка, мерж закрыт.
- **Нашёл протечку — чини, а не заглушай.** Протокол исправления (куда выносить
  зависимость, как разворачивать направление) —
  [.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md).
  Игнор-строки в `.importlinter` добавляются только с обоснованием в PR и ADR.

## Чек-лист при изменении структуры

- [ ] Новый каталог/модуль однозначно отнесён к слою из таблицы выше.
- [ ] Не появился импорт «наружу» и между платформами — подтверждено `lint-imports`.
- [ ] Нет `if platform == …` вне `infrastructure/platforms/`.
- [ ] Изменение самих границ оформлено как ADR ([../decisions/README.md](../decisions/README.md))
      и отражено в этом документе.
- [ ] Таблица пакетов и дерево выше актуальны.
