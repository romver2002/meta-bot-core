---
status: active
version: "1.25"
updated: 2026-07-26
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

- 2026-07-06 — строгий контур CA: [.importlinter](../../.importlinter) (6 контрактов) + CI [arch-lint](../../.github/workflows/arch-lint.yml)/[ci.yml](../../.github/workflows/ci.yml) (ruff/mypy/pytest, coverage ≥90%); статусы ADR — в реестре [decisions/README](../decisions/README.md) (перечислять их здесь нельзя: разъезжаются).
- 2026-07-08 — бэкенд по канону CA (Python 3.14 + uv, PG16+Redis7): domain (Bot/Flow/Session, BR-001/003/006), хранение ADR-0008, Flow Engine, адаптеры Telegram/MAX, webhook с идемпотентностью, Admin API. Гейт зелёный: ruff · mypy strict · lint-imports 6 контрактов · 81 unit + 4 integration · e2e золотого пути + живой смоук.
- 2026-07-08/09 — mini app end-to-end (auth init data BR-007, `open_mini_app`, `mini_app_result`, привязка к боту), блок `http_request` (`{{secret:*}}` за портом); первый бот «умный помощник по заявкам» как Flow-данные ([examples/first-bot-request-assistant/](../../examples/first-bot-request-assistant/)) с живым AI-ответом (OpenRouter), live-smoke в Telegram пройден; must-fix остаточной `http_request`-переменной починен + регресс-тест.
- 2026-07-10 — блок `notify` (ADR-0010: роль → адресат за `NotificationTargetResolverPort`, best-effort, `PUT /notifications/{role}`, антиспуфинг карточки); `answer_callback` + `IncomingEvent.callback_id` (гасит спиннер; TG — id в теле, MAX — в query; различия только в адаптерах, MockTransport-контракты); **BR-008/ADR-0011, ПДн**: стирание `variables` при завершении/просрочке, фоновая чистка (`PurgeExpiredSessionsUseCase` за `SessionRetentionPort`), экраны согласия в примере first-bot.
- 2026-07-09..11 — `frontend/constructor/` актуализирован под живой Flow Engine/API (Engine v1 palette включая `notify`, `trigger.config`, `http_request`, панель «Боты и публикация», стартовый шаблон, безопасный путь публикации со скрытыми bot_id/row_version): кнопочные переходы видны на холсте; адаптивные связи, групповое выделение/копирование/удаление не меняют Flow-данные, снятие выделения чистит буфер, счётчик узлы/связи раздельный; FastAPI-ошибки нормализуются, проблемы публикации подсвечивают узлы, Error Boundary, drawer на мобильных; ширина панелей регулируется на десктопе (только localStorage, в Flow/API не входит). Гейты: `npm test` 16 и production build зелёные.
- 2026-07-11 — ADR-0012 edit-in-place (ответ на нажатие правит сообщение с меню на месте, фолбэк — отправка+удаление; `edit_message`/`delete_message` в `BotPlatformPort`, различия платформ только в адаптерах); read-контракт черновика `GET /api/bots/{id}/flow` (204 — черновика нет; пустое `name` не сбрасывает имя; не-UUID id → 404); `ask` с вариантами быстрого ответа (payload = значение, свободный текст равноправен; в примере first-bot услуга/срок/бюджет кнопками, вилки бюджета от услуги). Гейт: 206 unit, mypy strict, 6/6 контрактов.
- 2026-07-11 — по вопросам владельца: ADR-0013 структурное логирование (JSON+request_id, stdout + локальные `logs/app.log`/`errors.log`, единый 500, WARN вместо молчаливых подавлений), типизированный исход вебхука (enum `WebhookOutcome`), [deployment.md](../architecture/deployment.md) (топология «мультитенантный движок, бот = данные»), раздел «Размещение» в ADR-0006, политика актуальности стека в tech-stack.md. Демо-инцидент разобран по errors.log: контейнерный `.secrets/` стёрся при пересоздании — `./.secrets` теперь смонтирован с хоста, сертификат Минцифры vendored в `ops/certs/` + Dockerfile.
- 2026-07-12 — `frontend/miniapp/`: отдельный TypeScript 7/Vite 8 пакет без runtime-зависимостей; общий `MiniAppPlatform` bridge Telegram/MAX/Browser, backend auth/result API-клиент, точный CORS allowlist, Vite CI. `initData` не логируется и не сохраняется; 16 Vitest зелёные, production initial bundle — JS 4.55 KiB gzip, CSS 2.15 KiB gzip (автоматический budget).

## В работе

<!-- Начато, но не завершено; в каком состоянии оставлено и что дальше. -->

- 2026-07-08 — ратификация ADR-черновиков (`proposed` в реестре [decisions/README](../decisions/README.md), ждут команды); следом — песочница custom_code. Открытие существующего Flow в редакторе закрыто (7ea5ae6, ADR-0015): `getFlowDraft` + восстановление layout.

## Известные проблемы

<!-- Живые баги и ограничения, о которых надо знать до начала работы.
     Починено → строку удалить. -->

| Проблема | Влияние | Обходной путь | Issue |
|---|---|---|---|
| Нет IAM: Admin API без аутентификации; token vault — dev-файл (`.secrets/`) | Контур только для доверенной среды разработки | Auth и прод-vault — открытые вопросы active-context; порты позволяют заменить без правки ядра | — |
| Блок custom_code движком не исполняется | Сценарии с ним не публикуются (BR-006 по CapabilityMatrix v1) | Реализуется своим этапом (песочница ADR-0003) | — |
| 2026-07-10 — catch-all TEXT-триггер уводит сессию с узла-ожидания кнопок (show_buttons) — его кнопки перестают матчиться | Кнопки «умирают» после свободного текста | В данных — фолбэк callback-триггеры (+guard), как в примере first-bot; системно — правило приоритета маршрутизации, кандидат в BR | — |
| 2026-07-26 — перманентный отказ доставки не отличим от временного: адресат роли без открытого диалога даёт MAX `404 dialog.not.found`, а наружу это тот же `502`, что и сбой платформы. Push-событие при этом теряется — очереди/повтора у `/events` нет | Внешний потребитель (радар) шлёт карточки «в никуда» и узнаёт об этом только по коду ответа; ретрай не поможет — нужен человек | Проверять адресата пробной отправкой при регистрации роли; системно — отдельный класс ошибки «адресат недостижим» + отложенная очередь (кандидат в ADR к 0010/0017) | — |

## Расхождения база↔код

<!-- Сюда агенты фиксируют найденные противоречия между документами базы и кодом
     (или между документами) — НЕ исправляя их молча, см. [../_meta/lifecycle.md](../_meta/lifecycle.md).
     Расхождение устранено (документ или код поправлен) → строку удалить. -->

| Документ | Что расходится | Кто заметил | Дата |
|---|---|---|---|
| [decisions/0008-persistence-model.md](../decisions/0008-persistence-model.md) | обещает hot-FSM Session в Redis (`session:{bot_id}:{user_id}`, write-through, лок) — в коде сессии только в PG, Redis лишь идемпотентность вебхуков; реализовать Redis-FSM или скорректировать ADR при ратификации | agent | 2026-07-11 |
| [decisions/0008-persistence-model.md](../decisions/0008-persistence-model.md) | имена методов портов в §Решение (блок «Порты») (`get_published`/`load_version`, `find_active`/`start`/`finish`/`expire`) разошлись с кодом (`get_version`/`list_versions`, `get_active`/`save`; ретеншен — `SessionRetentionPort`) — синхронизировать при ратификации | agent | 2026-07-12 |
| [architecture/tech-stack.md](../architecture/tech-stack.md) | frontend React 18.3/Vite 5.4 против политики актуальности стека (2026-07-11): поднять до React 19/Vite 7 (+`@xyflow/react` 12.4+) или зафиксировать исключение в ADR-0007 (proposed) — решение владельца | agent | 2026-07-12 |
| — (открытый гэп, не расхождение текста) | У ядра нет механизма, не дающего опубликовать сценарий одного продукта в бота другого. Кандидаты: правило публикации (Flow с `external_event` + публичные входы start/text/callback в одной цепочке — подозрительно) и сверка опубликованного `definition_hash` с эталоном `examples/`. Пока защита живёт вне ядра — в скриптах деплоя обоих продуктов, по маркерным узлам | agent | 2026-07-26 |
| [decisions/0011-session-pii-retention.md](../decisions/0011-session-pii-retention.md) | `purge_expired_sessions` и `SessionRepositoryPort` обещают стирать `external_chat_id` как ПДн, но такого поля у доменной `Session` нет вовсе: колонка `session.external_chat_id` в ORM ([models.py](../../src/infrastructure/db/models.py)) никогда не пишется и всегда NULL (проверено на живой БД). Либо убрать мёртвую колонку миграцией и поправить тексты, либо завести поле осознанно | agent | 2026-07-26 |
| architecture/security.md | Секрет вебхука ОДИН на все продукты (settings.webhook_secret), а bot_id берётся из URL и с платформенной личностью бота не сверяется: владелец секрета может подать update в любого бота инстанса. Изоляция продуктов на этом входе держится только на неразглашении общего секрета. Лечение — пер-ботовый секрет при publish в token_vault + сверка id платформенного бота (verify_token уже дёргается); объём ADR-уровня, отдельная задача. | agent | 2026-07-26 |

## Технический долг

<!-- Только крупные пункты, влияющие на планирование. Мелочь — в issue-трекер.
     У каждого пункта — ссылка на issue и почему это долг (какое правило нарушено). -->

- 2026-07-06 — не выбрано прод-хранилище секретов за `TokenVaultPort` (блокирует BR-004/BR-007); пороги покрытия не ратифицированы (в CI ≥90% domain/application).
- 2026-07-08 — отложено по аудиту (осознанно): (1) optimistic lock Bot между get/save — до IAM;
  (2) seed `capability_matrix` в БД — ждёт ратификации ADR-0005;
  (3) `session.flow_version_id/current_node_id` nullable вопреки design.md §1 (черновая сессия до первого шага).
- 2026-07-08 — перед релизом MAX сверить живым запросом 6 пунктов «требует проверки»
  из `specs/002-platform-deep-dive/report.md` §6 (`update_types`, 429, `callback_id`, `requestContact`, TTL initData). (Сертификат Минцифры с 2026-07-11 vendored в `ops/certs/` + Dockerfile — b4a167e, пункт про ручное добавление закрыт.)
- 2026-07-10 — MAX-адаптер чейнит httpx-ошибку (`from exc`): request в `__cause__` держит Authorization — не логировать цепочку с интроспекцией request до скраба (TG уже скрабит).
- 2026-07-26 — Ядро не умеет переименовать бота: имени задаётся только при connect, эндпоинта rename нет, а name в PUT /bots/{id}/flow — имя СЦЕНАРИЯ. Реестр «Мои боты» врёт: радар навсегда «MetaFlow MAX Smoke». Пара к уже записанному ADR-кандидату «явный признак продукта у бота»; до него защиты «мой ли это бот» опираются на содержимое сценария, не на имя (architecture/deployment.md).

---

<!-- Правила: записи и строки таблиц с датами YYYY-MM-DD, коротко, по факту;
     при каждом обновлении вычищать отработанное — починенное, устранённое, закрытый
     долг (история — в git); повторяющееся с известным лечением → ops/runbooks/,
     системные решения → decisions/; при содержательной правке поднимать version/updated. -->

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
