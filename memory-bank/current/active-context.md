---
status: active
version: "1.9"
updated: 2026-07-08
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

- 2026-07-06 — приняты (accepted) ADR-0001 «Clean Architecture + SOLID, строгий режим»
  ([../decisions/0001-clean-architecture.md](../decisions/0001-clean-architecture.md)) и ADR-0002
  «Доменное ядро + платформенные адаптеры» ([../decisions/0002-domain-core-and-adapters.md](../decisions/0002-domain-core-and-adapters.md)) — фундамент.
- 2026-07-06 — ADR-0003..0006 (движок на блоках + песочница, webhook, capability matrix,
  mini app как web-продукт) — черновики `proposed`, ждут ратификации командой
  ([../decisions/README.md](../decisions/README.md)).
- 2026-07-07 — решено: интеграцию MAX делаем **сразу на `platform-api2.max.ru`**
  (проект greenfield); старый `platform-api.max.ru` не используем, «миграции» нет.
  Токен MAX — в заголовке `Authorization`; в доверенные добавляется сертификат Минцифры
  ([../architecture/platform-reference.md](../architecture/platform-reference.md),
  [../ops/configuration.md](../ops/configuration.md)).
- 2026-07-08 — Каркас визуального редактора сценариев на React + React Flow (frontend/constructor): палитра 4 триггеров + 8 блоков, холст с переходами, панель настройки, гейт публикации BR-001, JSON-панель Flow. npm build ок (202 модуля), dev-сервер 200. ADR-0007 (proposed) + синхронизированы индексы.
- 2026-07-08 — Вертикальный срез бэкенда: src/ по канону CA (domain: Bot/Flow/Session+BR-001/003/006; application: 6 портов + CreateBot/PublishBot; presentation: health; infrastructure: скелет). Стек поднят по образцу sro-agent-core (решение Романа): Python 3.14, uv+uv.lock, hatchling/hatch-vcs, pytest 9, ruff 0.14 ALL, Dockerfile+compose (PG16+Redis7). Всё зелёное: ruff, mypy strict, lint-imports 5/5, pytest 32. ADR-0008 (proposed) + specs/001-persistence/design.md
- 2026-07-08 — Хранение по ADR-0008: модели/мапперы/Pg-репозитории (версии Flow, оптимистический лок, partial-unique активной Session), Alembic 0001. Гейт: ruff/mypy/lint-imports/pytest 32 unit + 4 integration (testcontainers, PG16) — зелёные.

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
- 2026-07-08 — Первый реальный кейс после MVP конструктора — интернет-магазин с корзиной внутри Telegram/MAX: mini app-витрина (core/cart+core/catalog по ADR-0006), воронка в боте из блоков, платежи как platform-specific возможность по CapabilityMatrix, товары/заказы — отдельный bounded context Shop (ядро про них не знает).
- 2026-07-08 — Реализовать infrastructure/db по ADR-0008 (models/mappers/repositories, Alembic, интеграционные тесты testcontainers) и admin_routes + webhook_routes; фронт-редактор подключить к Admin API
- 2026-07-08 — MaxBotAdapter: оценить SDK maxapi (github.com/love-apples/maxapi — MIT, живая v1.2.1, aiogram-стиль на aiohttp) против тонкого httpx-клиента; проверить, что SDK ходит на platform-api2.max.ru (токен в Authorization); Dispatcher/Router не нужны — роутит Flow Engine; решение оформить как ADR-0009 по правилу зависимостей tech-stack.md
- 2026-07-08 — Рендеринг исходящих сообщений (Message Dispatcher/адаптеры): использовать Templater/ (локальный референс, BigPixelLab) как источник дизайна декларативного описания сообщения (текст+клавиатуры+if/for+вложенные шаблоны); код НЕ вендорить — нет лицензии, eval() на данных, привязка к aiogram; писать нейтральную модель + рендер в адаптерах

## Открытые вопросы к команде

<!-- Вопрос блокирует работу? Получен ответ → удалить, решение зафиксировать выше. -->

- 2026-07-06 — менеджер зависимостей и lock-файл: poetry или uv? (уточнить у команды).
- 2026-07-06 — хранилище секретов за `TokenVaultPort` (token vault) — какое? (уточнить у команды).
- 2026-07-06 — пороги покрытия тестами в CI — какой минимум? (уточнить у команды).

---

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
