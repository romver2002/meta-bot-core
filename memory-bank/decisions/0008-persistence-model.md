---
status: active
version: "1.0"
updated: 2026-07-08
verified_commit: ""
owner: ""
decision_status: proposed
---

# ADR-0008: Модель хранения (persistence): версии Flow в JSONB, Session в PG+Redis

> Черновик на ратификацию командой. `accepted` ставит владелец раздела.
> Полный пакет (DDL, форматы Redis-ключей, сигнатуры портов, эскиз SQLAlchemy,
> Alembic, чек-лист сборки) — рабочий артефакт `specs/001-persistence/design.md`.

## Контекст

Домен зафиксирован (Bot/Flow/Session, ADR-0002; движок на блоках, ADR-0003), начат
вертикальный срез бэкенда — нужна схема хранения. По Clean Architecture БД — деталь
`infrastructure/` за портами-репозиториями: схема выводится из доменной модели, а не
наоборот. Ключевые силы: Flow — это данные-граф (редактор шлёт документ целиком);
публикация требует стабильной исполняемой версии, пока черновик правится; Session —
горячее FSM-состояние (p95 вебхука ≤500 мс) при durable-восстановлении; токены — секреты
(не в основной БД); идемпотентность вебхуков (ADR-0004); версионирование custom_code (BR-004).

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. JSONB-документ (Flow одной колонкой) | Просто; совпадает с «Flow — данные»; легко сохранять целиком | Нет разделения Draft/Published; публикация правит исполняемое |
| 2. Полная нормализация (таблицы nodes/transitions/buttons) | Реляционные гарантии, запросы по блокам | Дорогое чтение/запись агрегата целиком; редактор работает документом; версионирование мучительно |
| 3. **Гибрид с версионированием** (тонкий head + иммутабельные `flow_versions` c JSONB) | Draft и Published разделены; рантайм читает замороженную версию одним SELECT; аудит и откат бесплатно | Чуть больше таблиц; нужна дисциплина иммутабельности версий |

## Решение

Принят **вариант 3** (победитель жюри) с переносами из проигравших: оптимистический лок
черновика (`row_version`), GIN `jsonb_path_ops`, `capability_matrix` как seed-данные, CHECK
как defense-in-depth (авторитет инвариантов — домен).

- **Postgres 16**: `bot` (платформа, `token_vault_ref`, `published_flow_version_id`),
  `mini_app` (0..1 на бота, CHECK https — BR-003), `flow` (head) + `flow_versions`
  (иммутабельные версии: `definition` JSONB — весь граф, `schema_version`, `content_hash`,
  ровно один draft через partial-unique), `custom_code_versions` (append-only, пин
  `(code_id, version)` в definition — BR-004), `session` (durable-снапшот FSM;
  partial-unique «одна активная на (bot, пользователь)»), `publish_audit` (append-only
  журнал lifecycle), `capability_matrix` (данные BR-006). Внутри агрегата — жёсткие FK;
  между агрегатами — ссылки по id без FK (границы агрегатов = границы транзакций).
- **Redis 7**: горячий FSM `session:{bot_id}:{user_id}` (idle-TTL, write-through в PG),
  лок единственности сессии, идемпотентность `idemp:{platform}:{bot_id}:{update_id}`
  (`SET NX EX`, 24 ч). Отдельной таблицы идемпотентности в PG нет.
- **Токены**: в `bot` — только `token_vault_ref`; значение живёт исключительно за
  `TokenVaultPort`; init data mini app не хранится вовсе (BR-007).
- **ORM**: SQLAlchemy 2 async; домен не наследует `Base` — маппер на границе
  (`infrastructure/db/models.py` + `mappers.py`). Миграции — Alembic.
- **Порты** расширяются под версии: `FlowRepository.get_draft/save_draft/publish/
  get_published/load_version/list_versions`; `SessionRepository.find_active/start/save/
  finish/expire`; `Session` пинит `flow_version_id` (активная сессия доигрывает свою версию).

Граница решения: только `infrastructure/` и контракты портов; domain/application про
Postgres/Redis не знают (контролирует import-linter).

## Последствия

**Положительные:**
- Публикация не трогает исполняемое: рантайм читает иммутабельную версию, редактор — черновик.
- Откат/аудит публикаций встроены (`publish_audit`, `published_flow_version_id`).
- Новые типы блоков не требуют DDL-миграций (definition JSONB + `schema_version`).

**Отрицательные:**
- Больше таблиц и дисциплины (иммутабельность версий держит репозиторий).
- Запросы «внутрь» графа — через GIN/JSONB, не реляционные JOIN'ы.

**Риски:**
- Дрейф формата `definition` → `schema_version` + app-миграции формата, контрактный тест.
- Расхождение Redis↔PG у Session → write-through + регидрация из PG (источник правды — PG).
- Расхождение с глоссарием: порт `BotRepository` канон не содержит, а агрегат Bot его
  требует — зафиксировано в progress.md, вносится в glossary/patterns при ратификации.

**Открытые вопросы:** бэкенд token vault; ретеншн/маскирование ПДн (`external_user_id`,
`variables`) по 152-ФЗ; `owner_id`/RBAC (мульти-тенантность).

## Ссылки

- `specs/001-persistence/design.md` — полный пакет (DDL, Redis, порты, Alembic, чек-лист)
- [0002-domain-core-and-adapters.md](0002-domain-core-and-adapters.md), [0003-flow-engine-blocks-and-sandbox.md](0003-flow-engine-blocks-and-sandbox.md), [0004-webhook-platform-integration.md](0004-webhook-platform-integration.md)
- [../domain/domain-model.md](../domain/domain-model.md) — агрегаты и инварианты
- [../architecture/security.md](../architecture/security.md) — токены и секреты
- [../architecture/tech-stack.md](../architecture/tech-stack.md) — PG 16, SQLAlchemy 2, Redis 7
