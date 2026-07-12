---
status: active
version: "1.2"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Стратегия тестирования

Как meta-bot-core проверяет корректность по слоям Clean Architecture
([overview.md](overview.md)). Стек тестов — pytest поверх Python 3.14 (async):
domain/application как быстрые тесты без I/O, infrastructure — интеграционные
против реальных Postgres 16 / Redis 7 через testcontainers и фейкового HTTP
платформ. Когда какие тесты обязательны по процессу —
[../workflows/new-feature.md](../workflows/new-feature.md),
[../workflows/bug-fix.md](../workflows/bug-fix.md).

## Пирамида по слоям

| Уровень | Слой | Что проверяем | Изоляция |
|---|---|---|---|
| unit | domain | инварианты `Bot`, `Flow`, `Node`, `Session` и бизнес-правила BR-001..BR-007 ([../domain/business-rules.md](../domain/business-rules.md)): публикуемость `Bot` (BR-001), HTTPS-URL и привязка `MiniApp` к боту (BR-003), валидация `Flow` по `CapabilityMatrix` (BR-006) | без инфраструктуры вообще — домен не знает о ней по построению |
| unit | application | сценарии use case: `ProcessUpdateUseCase`, `PublishBotUseCase`, `CreateBotUseCase` — ветвления, классы ошибок, порядок вызовов портов | порты (`BotPlatformPort`, `FlowRepository`, `SessionRepository`, `TokenVaultPort`, `CodeExecutorPort`) подменяются in-memory фейками |
| integration | infrastructure | репозитории (`FlowRepository`, `SessionRepository`) против реальной БД/Redis; адаптеры `TelegramBotAdapter`/`MaxBotAdapter` против фейкового HTTP; `CodeExecutorPort` — изоляция и таймаут песочницы (BR-004); `mini_app_auth` — валидация init data (BR-007) | реальные Postgres 16 / Redis 7 через testcontainers; внешний HTTP платформ — фейковый сервер, реальные токены не используются |
| e2e | весь стек | критические пути: приём вебхука → ответ бота; публикация бота (BR-001); открытие mini app с валидацией init data (BR-007) | окружение, близкое к prod |

Чем ниже слой — тем больше тестов; e2e — только критические пути, не «всё подряд».

## Что покрывается обязательно

- Каждое бизнес-правило из [business-rules.md](../domain/business-rules.md) —
  тестом со ссылкой на номер BR в имени или докстринге. Уровень зависит от природы
  правила (таблица ниже): доменный инвариант — unit domain; правило, требующее
  инфраструктуры (песочница, mini app-авторизация) — интеграционный тест;
  запрет ветвления по платформе (BR-005) — не pytest, а арх-линтер.
- Каждый use case — happy path плюс каждый класс ошибок, порты замоканы фейками.
- Каждый багфикс — регрессионный тест, падающий до фикса
  ([../workflows/bug-fix.md](../workflows/bug-fix.md)).
- Каждая реализация репозитория (`FlowRepository`, `SessionRepository`) —
  интеграционный тест контракта интерфейса против реальной БД.

Привязка BR → уровень (источник привязки «правило ↔ тест» —
[business-rules.md](../domain/business-rules.md); точные пути файлов, кроме
зафиксированных в реестре, — уточнить у команды):

| BR | Уровень | Где проверяется |
|---|---|---|
| BR-001 | unit domain + e2e | `src/domain/bot/entities.py::Bot.publish` → `tests/unit/bot/test_bot_publish.py`; критический путь публикации — e2e |
| BR-002 | unit application | политика создания `Bot` только по токену в `CreateBotUseCase` |
| BR-003 | unit domain | `MiniApp`: только HTTPS-URL и обязательная привязка к боту |
| BR-004 | integration | `CodeExecutorPort` + `src/infrastructure/code_executor/`: изоляция, таймаут 1–3 c, лимит памяти/размера ответа ([ADR-0003](../decisions/0003-flow-engine-blocks-and-sandbox.md)) |
| BR-005 | arch-lint (import-linter) | контракт `.importlinter`, джоба `arch-lint`; проверяет отсутствие `if platform == …` вне `infrastructure/platforms/` |
| BR-006 | unit domain | `Flow.validate` по `CapabilityMatrix`: недоступный блок отклоняется при публикации |
| BR-007 | integration | `src/infrastructure/platforms/*/mini_app_auth.py`: валидация init data (подпись Telegram / данные MAX Bridge) до доверия пользователю |

BR-005 автоматически проверяет import-linter, а не тест: детали границ и джобы —
[overview.md](overview.md) и
[../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml).

## Пороги покрытия

Инструмент подсчёта — pytest-cov (точная конфигурация — уточнить у команды).

- **domain + application — ≥ 90% line coverage, гейт в CI**: падение ниже порога
  закрывает мерж. Именно эти слои содержат бизнес-логику и покрываются дёшево.
- **infrastructure и presentation — без жёсткого процента**, но обязательны
  интеграционные тесты для каждого репозитория и каждого платформенного адаптера,
  для песочницы (BR-004) и для mini app-авторизации (BR-007).
- Из подсчёта исключаются DTO/схемы, миграции БД и composition root
  (`src/main.py`) — там нет ветвлений логики (список исключений — уточнить у команды).

## Как запускать

Прогон — через pytest-маркеры (`unit`/`integration`/`e2e`); обёртки в `make` и
точные таргеты — уточнить у команды.

| Что | Команда |
|---|---|
| unit — быстрые, перед каждым коммитом | `pytest -m unit` (напр. `make test-unit`) |
| integration — требуется docker (testcontainers: Postgres 16, Redis 7) | `pytest -m integration` (напр. `make test-integration`) |
| e2e | `pytest -m e2e` (напр. `make test-e2e`) |
| всё + coverage (как в CI) | `pytest --cov=domain --cov=application` с гейтом ≥ 90% (напр. `make test`) |

## Правила

- Тест, зависящий от порядка выполнения, реального времени или сети, — дефект.
  Внешний HTTP платформ в интеграционных тестах — только фейковый сервер.
- Flaky-тест не перезапускаем «до зелёного», а чиним; если чинить сейчас нельзя —
  помечаем и заводим задачу ([../current/progress.md](../current/progress.md)).
- Тестовые данные — через фабрики/фикстуры (расположение — `tests/`, точное место
  уточнить у команды); домен и use cases используют in-memory фейки портов.
- Токены ботов и init-данные mini app — секреты: реальные значения в тестах
  запрещены, только фейки/фикстуры ([security.md](security.md)).
