---
status: active
version: "1.39"
updated: 2026-07-12
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

- Живой контур работает: два бота (Telegram/MAX) на одном мультитенантном движке,
  первый сценарий «умный помощник по заявкам» в `examples/`; модель «бот = данные» —
  [../architecture/deployment.md](../architecture/deployment.md).
- Ближайшее в конструкторе — открытие существующего сценария (`getFlowDraft`).
  Mini app runtime уже выделен в `frontend/miniapp/`: общий лёгкий TypeScript
  shell + bridge Telegram/MAX/Browser, CORS и CI (ADR-0006 accepted); витрина и
  корзина остаются отдельным следующим продуктовым этапом.
- Фундамент неизменен: строгая Clean Architecture, границы слоёв держит
  import-linter в CI ([../architecture/overview.md](../architecture/overview.md)).

## Последние решения и договорённости

<!-- Список с датами, ~10 строк. Старше пары недель — в decisions/ или удалить. -->

- 2026-07-06..08 — фундамент: ADR-0001/0002 accepted (строгая CA; ядро + адаптеры); вертикальный срез бэкенда ADR-0008/0009 (Pg + optimistic lock + Alembic, адаптеры TG/MAX, webhook + Redis, Admin API, Flow Engine); стек Python 3.14/uv/PG16+Redis7 по образцу sro-agent-core (решение Романа); MAX сразу на `platform-api2.max.ru`, токен в `Authorization`; гейт покрытия в CI ≥90% (domain/application).
- 2026-07-08 — mini app end-to-end (бэкенд): auth init data BR-007 (общее HMAC-ядро TG/MAX), блок `open_mini_app`, триггер `mini_app_result`, привязка к боту; живой смоук 200/401/401.
- 2026-07-09 — первый бот «умный помощник по заявкам» жив в Telegram (examples/, live-smoke); конструктор актуализирован под Engine v1 (catalog, `http_request`, панель «Боты и публикация»).
- 2026-07-10 — блок `notify` (ADR-0010): доставка третьему лицу по роли за `NotificationTargetResolverPort`, best-effort; `answer_callback` гасит спиннер на TG/MAX; BR-008/ADR-0011 — ретеншен и стирание ПДн сессий (фоновая чистка, согласие в примере, хэш MAX-ключей идемпотентности).
- 2026-07-10..11 — конструктор: рамка/Ctrl-выделение, копирование с очисткой буфера, массовое удаление, нормализация ошибок API (422 по полям, безопасные 404/409/5xx/offline), Error Boundary, настраиваемые панели; npm test 16 + build зелёные.
- 2026-07-11 — ADR-0012 edit-in-place: ответ на callback правит меню на месте (порт edit/delete_message, адаптеры TG/MAX, фолбэк отправка+удаление); рой-проверка доков опровергла 4 утверждения чата — лимиты зафиксированы в platform-reference.
- 2026-07-11 — read-контракт черновика: `GET /api/bots/{id}/flow` → definition+row_version; 204 — бот есть, черновика нет; 404 — только «бота нет»; не-UUID id → 404; пустое name не сбрасывает имя.
- 2026-07-11 — синхронизация memory-bank с mb-kit 5e840f8 (монотонный bump, setup/hook, LF/UTF-8, CI); 86 self-tests зелёные.
- 2026-07-11 — ADR-0013 структурное логирование (JSON+request_id, logs/errors.log, скраб токена, enum WebhookOutcome) + deployment.md + размещение mini app в ADR-0006; 218 unit; коммиты ea2d32e+95b6d95.
- 2026-07-11 — демо-инцидент «/start молчит» разобран по errors.log (KeyError vault): `.secrets` переведён на хост-маунт, сертификат Минцифры vendored в ops/certs + Dockerfile; оба бота живые (b4a167e).
- 2026-07-12 — Сценарий отдельной поставки клиенту (self-hosted) зафиксирован в architecture/deployment.md: тот же движок без форка, состав бандла, gap-лист (экспорт/импорт бота, публичный образ, инструкция); проверено утверждение 'везде print' — в src/tests 0 (ruff T201 в CI), print только в scripts/ CLI-утилитах
- 2026-07-12 — Многоагентное ревью архитектуры БД и стратегии (72 агента, адверсариальная верификация): схема корректна, потолок не в БД (нет кэша definition, rate-limits платформ не реализованы); переносимость БД подтверждена (~1050 строк в одном слое infrastructure/db); топология — один мультитенантный сервис (deployment.md); mini app: backend готов end-to-end, фронта нет; CRM: «без потери» сегодня не выполняется — заявка эфемерна (session.variables стираются после best-effort notify). Код не менялся
- 2026-07-12 — Аудит и синхронизация базы знаний с кодом (рой 72+20 агентов): 58 подтверждённых расхождений исправлены в 20 файлах — фантомные имена (RunFlowUseCase/SendMessageUseCase/ExecuteNodeUseCase/FileStoragePort -> реальные), статус custom_code/песочницы 'план' (BR-004, ADR-0003, security, tech-stack), реестр configuration.md + .env.example (7 недостающих переменных вкл. WEBHOOK_SECRET, 7 фантомных помечены планом), security.md приведён к факту (auth отсутствует), 6 контрактов importlinter, greenfield MAX вместо 'миграции', Redis=идемпотентность (FSM — план); нерешаемое без владельца — в progress.md 'Расхождения'
- 2026-07-12 — ADR-0006 ратифицирован: `frontend/miniapp/` — framework-free TypeScript 7/Vite 8 runtime; bridge загружается лениво для Telegram/MAX, Browser остаётся безопасным preview; init data не хранится на клиенте, CORS — точный allowlist. 16 Vitest зелёные, initial bundle: JS 4.55 KiB gzip, CSS 2.15 KiB gzip.
- 2026-07-12 — Пост-верификация синхронизации (рой 34 агента): 5 моих ошибок исправлены (WEBHOOK_BASE_URL план→реестр, §API→§Решение ADR-0008, счётчик тестов→устойчивая формулировка); закрыты пробелы индекса README (ADR-0014, backup-restore.md — их добавил параллельный контур mini app/webhook/CORS/backup). Дерево устаканилось: ruff зелёный, lint-imports 6/6, 241 unit. Коммит не делал — политика policy_commit: ask, явной команды не было
- 2026-07-12 — ADR-0014: авто-регистрация вебхука при publish (WEBHOOK_BASE_URL, register_webhook в порту+адаптерах TG/MAX); CORS для mini app (CORS_ALLOWED_ORIGINS, канонизация origin, валидация WEBHOOK_SECRET); каркас frontend/miniapp (bridge TG/MAX/Browser); этап 0 CRM в first-bot (http_request до wipe + error-ветка); бэкапы PG (pg-backup + runbook). Рой-ревью 5 областей: 7 should-fix вложено, bot_id-находка отклонена (uuid.UUID нормализует). Гейты: 255 unit, mypy strict, ruff, lint-imports 6/6, miniapp build+vitest 16

## Следующие шаги

<!-- Конкретные ближайшие действия, у каждого понятен результат. Не бэклог. -->

- 2026-07-12 — **закоммитить недостающую половину ea2d32e**: обработчик 502 в
  `admin_routes.py` + `verify_token_error` в фейке лежат в рабочем дереве, а тест
  `test_publish_when_platform_unreachable_is_502` уже в HEAD — чистый checkout
  красный. Политика `policy_commit: ask` — нужна явная команда владельца.
- 2026-07-08 — ADR-0007 вынести на ратификацию; при accepted — внести фронтенд-стек в architecture/tech-stack.md и описать контракт Admin API (CreateBot/PublishBot, обмен Flow).
- 2026-07-08 — рендеринг исходящих сообщений: Templater/ — референс дизайна декларативного описания (текст+клавиатуры+if/for+вложенные шаблоны); код НЕ вендорить (нет лицензии, eval() на данных, привязка к aiogram); нейтральная модель + рендер в адаптерах.
- 2026-07-12 — для первой витрины/формы определить предметный payload `mini_app_result`, экран и критерии бизнеса; runtime/bridge уже готовы, корзина и CRM-логика в каркас не вошли.
- 2026-07-11 — фронт-часть read-контракта: подключить `getFlowDraft` в редактор (открытие существующего сценария + восстановление layout из definition) — до этого редактор намеренно не предлагает открыть чужой/старый сценарий.
- 2026-07-12 — При первом запросе клиента на self-hosted закрыть gap-лист из deployment.md: экспорт/импорт бота, версионированный образ + compose-бандл в ops/, клиентская инструкция

## Открытые вопросы к команде

<!-- Вопрос блокирует работу? Получен ответ → удалить, решение зафиксировать выше. -->

- 2026-07-06 — хранилище секретов за `TokenVaultPort` для прода — какое? (dev —
  файлы `.secrets/` на хост-маунте; см. deployment.md «Чего не хватает до прода»).
- 2026-07-06 — пороги покрытия тестами: в CI де-факто гейт ≥90% (domain/application),
  командой не ратифицирован — подтвердить или изменить.

---

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
