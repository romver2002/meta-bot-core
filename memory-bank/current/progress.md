---
status: active
version: "1.14"
updated: 2026-07-10
verified_commit: ""
owner: ""
---

# Статус meta-bot-core

Живое состояние проекта: что стабильно, что в работе, что сломано, где база
знаний разошлась с кодом. Агент обновляет файл в конце каждой значимой сессии
автономно (см. [../_meta/governance.md](../_meta/governance.md)). Читается
обязательно перед работой над багом — см. [../README.md](../README.md).

## Работает

<!-- Что стабильно и на что можно опираться. Крупными блоками, не по коммитам. -->

- 2026-07-06 — строгий контур CA: [.importlinter](../../.importlinter) (6 контрактов) + CI
  [arch-lint](../../.github/workflows/arch-lint.yml)/[ci.yml](../../.github/workflows/ci.yml) (ruff/mypy/pytest, coverage ≥90%).
- 2026-07-06 — реестр ADR: 0001–0002 accepted, 0003–0009 proposed.
- 2026-07-08 — бэкенд по канону CA (Python 3.14 + uv, PG16+Redis7): domain (Bot/Flow/Session, BR-001/003/006), хранение ADR-0008, Flow Engine, адаптеры Telegram/MAX, webhook с идемпотентностью, Admin API. Гейт зелёный: ruff · mypy strict · lint-imports 6 контрактов · 81 unit + 4 integration · e2e золотого пути + живой смоук.
- 2026-07-09 — `frontend/constructor/` актуализирован под живой Flow Engine/API (Engine v1 palette, `trigger.config`, `http_request`, панель «Боты и публикация», стартовый шаблон помощника) + UX-исправления (закрываемые панели, вкладки, drawer на узких экранах).
- 2026-07-08 — mini app end-to-end: auth init data (BR-007), блок `open_mini_app`, триггер `mini_app_result`, привязка mini app к боту.
- 2026-07-09 — блок `http_request` (звонок в любой HTTP-API, `{{secret:*}}` за портом) + секреты подключения за портом; AI-ответ через OpenRouter выражается ДАННЫМИ Flow, без бото-специфики в ядре.
- 2026-07-09 — первый бот «умный помощник по заявкам» как Flow-данные ([examples/first-bot-request-assistant/](../../examples/first-bot-request-assistant/)): каркас + живой AI-ответ (OpenRouter) + форма; live-smoke в Telegram пройден (навигация/меню вживую). Движковый must-fix остаточной `http_request`-переменной (null-content → прошлый ответ) починен + регресс-тест.
- 2026-07-10 — блок `notify` (ADR-0010 proposed): доставка третьему лицу по символической роли за портом `NotificationTargetResolverPort`, best-effort; `PUT /notifications/{role}`; пример first-bot реально доставляет заявку админу/разработчику + catch-all подсказка. Рой-ревью (55 агентов): 2 must-fix починены (resolve вне try; мёртвые кнопки после catch-all-детура → guard-триггеры в данных), антиспуфинг карточки, атомарный общий JSON-store.
- 2026-07-10 — `BotPlatformPort.answer_callback` + `IncomingEvent.callback_id`: движок best-effort подтверждает каждое нажатие до guard'ов (гасит спиннер даже у бота на паузе); TG `answerCallbackQuery` (id в теле, скраб токена в ошибках) / MAX `POST /answers` (id в query) — различия только в адаптерах; MockTransport-контракты в тестах.
- 2026-07-10 — **BR-008 / ADR-0011, ПДн по закону**: завершение/просрочка сессии стирает `variables` (домен); фоновая чистка (`PurgeExpiredSessionsUseCase` за `SessionRetentionPort`) просрочивает зависшие FSM и удаляет завершённые сессии старше `SESSION_RETENTION_DAYS` целиком; в примере first-bot — экраны согласия перед сбором ПДн.
- 2026-07-10 — `frontend/constructor/`: кнопочные переходы видны на холсте (синхронизированы с `Button.target`),
  безопасный путь публикации (скрытые bot_id/row_version, лок платформы, проверка Mini App), палитра = Engine v1 включая `notify`; адаптивные связи и групповое выделение/копирование/удаление не меняют Flow-данные. FastAPI-ошибки нормализуются, все проблемы публикации подсвечивают узлы, запросы взаимно блокируются и есть Error Boundary; `npm test` (11) и build зелёные.

## В работе

<!-- Начато, но не завершено; в каком состоянии оставлено и что дальше. -->

- 2026-07-08 — ратификация ADR [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md)–[0011](../decisions/0011-session-pii-retention.md)
  (proposed, ждут команды). Следом — редактор ↔ Admin API, песочница custom_code.
- 2026-07-10 — read-контракт черновика и восстановление layout в редакторе:
  без него нельзя безопасно открыть и продолжить редактирование существующего Flow.

## Известные проблемы

<!-- Живые баги и ограничения, о которых надо знать до начала работы.
     Починено → строку удалить. -->

| Проблема | Влияние | Обходной путь | Issue |
|---|---|---|---|
| Нет IAM: Admin API без аутентификации; token vault — dev-файл (`.secrets/`) | Контур только для доверенной среды разработки | Auth и прод-vault — открытые вопросы active-context; порты позволяют заменить без правки ядра | — |
| Блок custom_code движком не исполняется | Сценарии с ним не публикуются (BR-006 по CapabilityMatrix v1) | Реализуется своим этапом (песочница ADR-0003) | — |
| 2026-07-10 — catch-all TEXT-триггер уводит сессию с узла-ожидания кнопок (show_buttons) — его кнопки перестают матчиться | Кнопки «умирают» после свободного текста | В данных — фолбэк callback-триггеры (+guard), как в примере first-bot; системно — правило приоритета маршрутизации, кандидат в BR | — |

## Расхождения база↔код

<!-- Сюда агенты фиксируют найденные противоречия между документами базы и кодом
     (или между документами) — НЕ исправляя их молча, см. [../_meta/lifecycle.md](../_meta/lifecycle.md).
     Расхождение устранено (документ или код поправлен) → строку удалить. -->

- 2026-07-08 — канон портов ([overview](../architecture/overview.md)) не содержит порты Admin API/webhook/mini
  app/http/notify (`BotRepository`, `IdempotencyPort`, `HttpClientPort`, `SecretResolverPort`, `NotificationTargetResolverPort`, UC) — внести при ратификации ADR-0008/0009/0010.

## Технический долг

<!-- Только крупные пункты, влияющие на планирование. Мелочь — в issue-трекер.
     У каждого пункта — ссылка на issue и почему это долг (какое правило нарушено). -->

- 2026-07-06 — не выбрано прод-хранилище секретов за `TokenVaultPort` — уточнить
  у команды; блокирует безопасную реализацию BR-004/BR-007 ([overview](../architecture/overview.md)).
- 2026-07-06 — пороги покрытия не ратифицированы (в CI действует ≥90% на domain/application).
- 2026-07-08 — отложено по аудиту (осознанно): (1) optimistic lock Bot между get/save — до IAM;
  (2) seed `capability_matrix` в БД — ждёт ратификации ADR-0005;
  (3) `session.flow_version_id/current_node_id` nullable вопреки design.md §1 (черновая сессия до первого шага).
- 2026-07-08 — перед релизом MAX сверить живым запросом 6 пунктов «требует проверки»
  из `specs/002-platform-deep-dive/report.md` §6 (`update_types`, 429, `callback_id`, `requestContact`, TTL initData).
- 2026-07-10 — TG-адаптер уже скрабит токен и рвёт цепочку исключений; MAX-адаптер
  чейнит httpx-ошибку (`from exc`) — request в `__cause__` держит Authorization-заголовок:
  не логировать цепочку с интроспекцией request до аналогичного скраба.

---

<!-- Правила: записи и строки таблиц с датами YYYY-MM-DD, коротко, по факту;
     при каждом обновлении вычищать отработанное — починенное, устранённое, закрытый
     долг (история — в git); повторяющееся с известным лечением → ops/runbooks/,
     системные решения → decisions/; при содержательной правке поднимать version/updated. -->

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
