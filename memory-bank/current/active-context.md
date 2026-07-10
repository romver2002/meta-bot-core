---
status: active
version: "1.26"
updated: 2026-07-10
verified_commit: ""
owner: ""
---

# Активный контекст meta-bot-core

Живой снимок «что происходит прямо сейчас». Агент читает его в начале каждой
сессии (протокол — в [../../AGENTS.md](../../AGENTS.md)) и обновляет в конце
каждой значимой сессии — автономно, без PR-ревью. Это единственный раздел
с такой автономией, см. [../_meta/governance.md](../_meta/governance.md).

## Текущий фокус

<!-- 1–3 пункта: что делаем сейчас и ПОЧЕМУ именно это (ссылка на roadmap/issue). -->

- 2026-07-06 — заведён проект meta-bot-core из шаблона базы знаний: наполняем
  `memory-bank/` реальным содержимым. Фундамент — строгая Clean Architecture
  ([../architecture/overview.md](../architecture/overview.md)); границы слоёв держит
  import-linter ([../../.importlinter](../../.importlinter)) в CI-джобе arch-lint
  ([../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)).
- 2026-07-06 — заложены доменные знания конструктора сценариев ботов Telegram/MAX
  (сущности, порты, бизнес-правила): [../domain/glossary.md](../domain/glossary.md),
  [../domain/business-rules.md](../domain/business-rules.md).

## Последние решения и договорённости

<!-- Список с датами, ~10 строк. Старше пары недель — в decisions/ или удалить. -->

- 2026-07-06 — ADR-0001/0002 (строгая CA; доменное ядро + адаптеры) — accepted,
  фундамент; ADR-0003..0006 — proposed, ждут ратификации ([../decisions/README.md](../decisions/README.md)).
- 2026-07-07 — интеграция MAX сразу на `platform-api2.max.ru` (старый хост не
  используем); токен MAX — в заголовке `Authorization`; сертификат Минцифры в доверенные
  ([../architecture/platform-reference.md](../architecture/platform-reference.md)).
- 2026-07-08 — Каркас визуального редактора сценариев на React + React Flow (frontend/constructor): палитра 4 триггеров + 8 блоков, холст с переходами, панель настройки, гейт публикации BR-001, JSON-панель Flow. npm build ок (202 модуля), dev-сервер 200. ADR-0007 (proposed) + синхронизированы индексы.
- 2026-07-08 — Вертикальный срез бэкенда: src/ по канону CA (domain: Bot/Flow/Session+BR-001/003/006; application: 6 портов + CreateBot/PublishBot; presentation: health; infrastructure: скелет). Стек поднят по образцу sro-agent-core (решение Романа): Python 3.14, uv+uv.lock, hatchling/hatch-vcs, pytest 9, ruff 0.14 ALL, Dockerfile+compose (PG16+Redis7). Всё зелёное: ruff, mypy strict, lint-imports 5/5, pytest 32. ADR-0008 (proposed) + specs/001-persistence/design.md
- 2026-07-08 — Хранение по ADR-0008: модели/мапперы/Pg-репозитории (версии Flow, оптимистический лок, partial-unique активной Session), Alembic 0001. Гейт: ruff/mypy/lint-imports/pytest 32 unit + 4 integration (testcontainers, PG16) — зелёные.
- 2026-07-08 — Адверсариальный аудит (50 агентов): 40 подтверждённых находок исправлено (TOCTOU публикации, идемпотентный publish, create-коллизия, завершение Session, non-root Docker, loopback-порты, CI с тестами и покрытием 96%); отложенное зафиксировано в progress. Гейт: 72 теста, mypy 52 файла, 6/6 контрактов
- 2026-07-08 — Живой контур: адаптеры Telegram/MAX (ADR-0009, тонкий httpx), webhook с идемпотентностью Redis, Admin API (create/flow/publish/get), Flow Engine подключён в composition root. Гейт: 84 теста (в т.ч. e2e золотого пути и живой смоук на PG), mypy 72 файла, 6/6 контрактов
- 2026-07-08 — Глубокое сравнение TG/MAX (рой, 55 агентов, 594 обращения к докам): отчёт specs/002-platform-deep-dive (38 confirmed/6 uncertain/2 refuted). Исправлено: ключ идемпотентности MaxBotAdapter на mid/callback_id; 2 ошибки в platform-reference (init data HMAC одинаков; у MAX нет платежей) + числа; чек-лист требует-проверки в progress
- 2026-07-08 — Валидация init data mini app (BR-007): общее HMAC-ядро webapp_signature (TG/MAX идентичны, из specs/002), per-platform обёртки, BotPlatformPort.validate_init_data, AuthenticateMiniAppUseCase, эндпоинт POST /api/bots/{id}/miniapp/auth. Гейт: 99 тестов (криптовекторы, срок, подделка, e2e через реальный адаптер) + живой смоук на контейнере (200/401/401).
- 2026-07-08 — Лоуп mini app: блок open_mini_app (движок шлёт кнопку запуска web_app/open_app и ждёт), триггер mini_app_result (эндпоинт результата -> движок продолжает сценарий), AttachMiniAppUseCase + эндпоинт привязки. CapabilityMatrix v1 расширена. Гейт: 117 unit, mypy 79, 6/6 контрактов.
- 2026-07-09 — первый бот 'умный помощник по заявкам' собран как Flow-данные (examples/), live-smoke пройден в Telegram (меню/навигация вживую); must-fix остаточной http_request-переменной (null-content → прошлый ответ) починен + регресс-тест
- 2026-07-09 — Актуализирован frontend/constructor по текущему Flow Engine/API конструктора: ruflo-аудит контракта, Engine v1 catalog без active custom_code, trigger.config, http_request JSON body/headers/response_map + error outcome, button targets, панель «Боты и публикация» (create/save row_version/publish/miniapp/secrets), стартовый шаблон умного помощника; npm build зелёный.
- 2026-07-09 — Исправлен UX frontend/constructor после замечаний: закрываемые палитра и правая панель, вкладки Настройки/Публикация, раскрываемые секции формы публикации, drawer-поведение на узких экранах, автопоказ настроек при добавлении/выборе блока; npm build зелёный.
- 2026-07-10 — Блок `notify` (ADR-0010 proposed): доставка третьему лицу по символической роли через `NotificationTargetResolverPort` + `BotPlatformPort.send_message`, best-effort (сбой резолва/доставки не рвёт цепочку); `PUT /api/bots/{id}/notifications/{role}`; пример first-bot реально доставляет заявку админу/разработчику + catch-all подсказка. Рой-ревью 55 агентов: 2 must-fix починены (resolve вне try; мёртвые кнопки после детура → guard-триггеры), антиспуфинг карточки, атомарный JSON-store.
- 2026-07-10 — `BotPlatformPort.answer_callback` + `IncomingEvent.callback_id`: движок best-effort подтверждает каждое нажатие до маршрутизации (гасит спиннер и у протухших кнопок); TG `answerCallbackQuery` (id в теле) / MAX `POST /answers` (id в query) — различия только в адаптерах; контракты закреплены MockTransport-тестами.
- 2026-07-10 — **BR-008/ADR-0011 (ПДн по закону)**: стирание переменных при завершении/просрочке; фоновая чистка (`SessionRetentionPort`, наблюдаемый цикл в `infrastructure/maintenance`); согласие + save-узлы-стиратели в примере (отмена стирает ПДн, дубль заявки блокируется guard'ом); MAX-ключи идемпотентности хэшируются; критерий простоя — `last_event_at`. Рой: 38 агентов, 11 подтверждённых находок вложено (включая must-fix «Отменить не стирает ПДн»).
- 2026-07-10 — Конструктор: адаптивные связи и рамка/Ctrl/⌘-выделение, групповое перемещение, безопасные Ctrl/⌘+C/V и массовое удаление; FastAPI 422 нормализуется по полям, 404/409/5xx и offline дают безопасные сообщения, все проблемы публикации видны на схеме и подсвечивают узлы. Добавлены единая блокировка API-действий, Error Boundary и корректное поведение drawer-панелей на мобильных; `npm test` (11) и production build зелёные.

## Следующие шаги

<!-- Конкретные ближайшие действия, у каждого понятен результат. Не бэклог. -->

- 2026-07-06 — вынести ADR-0003–0006 на решение команды; статус accepted/rejected
  проставляет человек ([../_meta/governance.md](../_meta/governance.md)).
- 2026-07-06 — начать MVP end-to-end: Admin UI → Webhook Gateway → Flow Engine →
  Message Dispatcher → Mini App ([../product/roadmap.md](../product/roadmap.md)).
- 2026-07-07 — `MaxBotAdapter` пишем сразу под `platform-api2.max.ru` (токен в
  `Authorization`, не в query); старый хост не поддерживаем. Внешний дедлайн
  платформы 2026-07-19 нас не блокирует — стартуем уже на v2.
- 2026-07-08 — ADR-0007 вынести на ратификацию; при accepted — внести фронтенд-стек в architecture/tech-stack.md и описать контракт Admin API (CreateBot/PublishBot, обмен Flow).
- 2026-07-10 — Не начинать отдельную Mini App-витрину/корзину: ближайший кейс —
  `first-bot-request-assistant`, где Flow собирает заявку до подтверждения и
  доставляет её админу; каталог, корзина и платежи остаются отложенными.
- 2026-07-08 — Реализовать infrastructure/db по ADR-0008 (models/mappers/repositories, Alembic, интеграционные тесты testcontainers) и admin_routes + webhook_routes; фронт-редактор подключить к Admin API
- 2026-07-08 — MaxBotAdapter: оценить SDK maxapi (github.com/love-apples/maxapi — MIT, живая v1.2.1, aiogram-стиль на aiohttp) против тонкого httpx-клиента; проверить, что SDK ходит на platform-api2.max.ru (токен в Authorization); Dispatcher/Router не нужны — роутит Flow Engine; решение оформить как ADR-0009 по правилу зависимостей tech-stack.md
- 2026-07-08 — Рендеринг исходящих сообщений (Message Dispatcher/адаптеры): использовать Templater/ (локальный референс, BigPixelLab) как источник дизайна декларативного описания сообщения (текст+клавиатуры+if/for+вложенные шаблоны); код НЕ вендорить — нет лицензии, eval() на данных, привязка к aiogram; писать нейтральную модель + рендер в адаптерах
- 2026-07-10 — для безопасного продолжения работы с уже существующим ботом нужен
  read-контракт черновика (`definition` + `row_version`) в Admin API и восстановление
  layout на фронте. До этого редактор намеренно не предлагает открыть чужой/старый
  сценарий, чтобы не перезаписать его стартовым шаблоном.

## Открытые вопросы к команде

<!-- Вопрос блокирует работу? Получен ответ → удалить, решение зафиксировать выше. -->

- 2026-07-06 — менеджер зависимостей и lock-файл: poetry или uv? (уточнить у команды).
- 2026-07-06 — хранилище секретов за `TokenVaultPort` (token vault) — какое? (уточнить у команды).
- 2026-07-06 — пороги покрытия тестами в CI — какой минимум? (уточнить у команды).

---

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
