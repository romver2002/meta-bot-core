Ниже — итоговый пакет решений. Возвращаю только Markdown.

---

# Пакет решений по хранению meta-bot-core

**Основа:** победитель жюри — **Hybrid-versioned** (28/28, тай-брейк в пользу версионирования), усиленный переносами из jsonb-doc (оптимистический лок, `jsonb_path_ops`, минимализм таблиц) и из Normalized (`capability_matrix` как данные, CHECK-защита в глубину, координаты редактора, CQRS-проекция под аналитику, интент композитного FK как доменная валидация + CI-гейт).

**Инвариант Clean Architecture (нерушимый):** всё ниже — деталь `infrastructure/`. `domain/` и `application/` про Postgres/Redis/SQLAlchemy не знают; персистентность видна им только через порты (`FlowRepository`, `SessionRepository`, `TokenVaultPort`, `CodeExecutorPort`, `FileStoragePort` — из глоссария). Границы проверяет `lint-imports` (`.importlinter`).

**Стойка агрегатов = стойка транзакций:** три корня — `Bot`, `Flow`, `Session`. Внутри агрегата — жёсткие FK; между агрегатами — ссылки по id (мягкие, без DB-FK). Единственное исключение из «FK внутри агрегата» — `bot ↔ mini_app` (mini_app в границе Bot).

---

## 1. Итоговая схема Postgres (DDL-эскиз)

```sql
-- ============ ENUM-типы (закрытые перечни из глоссария; имена = имена в коде) ============
CREATE TYPE platform_enum            AS ENUM ('telegram', 'max');                 -- расширяемо: VK, WhatsApp
CREATE TYPE bot_status_enum          AS ENUM ('draft', 'published', 'paused');
CREATE TYPE flow_version_status_enum AS ENUM ('draft', 'published', 'archived');
CREATE TYPE session_status_enum      AS ENUM ('active', 'completed', 'expired');
CREATE TYPE publish_action_enum      AS ENUM ('save_draft', 'publish', 'pause', 'resume', 'rollback');

-- ============ Агрегат Bot (корень) ============
CREATE TABLE bot (
    id                        uuid           PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id                  uuid           NULL,                       -- RBAC/multi-tenancy — open question, nullable
    platform                  platform_enum  NOT NULL,                   -- VO Platform, неизменяем после создания (BR-005)
    token_vault_ref           text           NOT NULL,                   -- ХЭНДЛ записи в token vault, НЕ секрет (см. §3)
    status                    bot_status_enum NOT NULL DEFAULT 'draft',  -- Draft→Published→Paused→Published
    flow_id                   uuid           NOT NULL,                   -- soft-ref на flow(id), 1—1 (кросс-агрегат, без DB-FK)
    published_flow_version_id uuid           NULL,                       -- soft-ref на flow_versions(id): исполняемая рантаймом версия
    created_at                timestamptz    NOT NULL DEFAULT now(),
    updated_at                timestamptz    NOT NULL DEFAULT now(),
    row_version               integer        NOT NULL DEFAULT 0,         -- оптимистическая блокировка агрегата
    CONSTRAINT uq_bot_flow UNIQUE (flow_id)                             -- связь Bot 1—1 Flow
);
-- BR-001 (валидный токен + Flow с ≥1 Trigger) проверяет домен Bot.publish, НЕ БД-триггер.
-- Порт BotRepository/MiniAppRepository в глоссарии НЕ заведён — расхождение, вынесено в ADR-0008.

-- ============ MiniApp (внутри агрегата Bot) ============
CREATE TABLE mini_app (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id     uuid        NOT NULL UNIQUE REFERENCES bot(id) ON DELETE CASCADE,  -- 0..1 на бота, в границе Bot
    url        text        NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_mini_app_https CHECK (url LIKE 'https://%')            -- BR-003, защита в глубину; авторитет — домен
);
-- init data mini app — секрет (BR-007): не хранится, валидируется на backend по подписи на лету.

-- ============ Агрегат Flow: тонкий head + иммутабельные версии ============
CREATE TABLE flow (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          uuid        NULL,
    bot_id            uuid        NULL,                                   -- обратная soft-ref (Bot 1—1 Flow)
    draft_version_id  uuid        NULL,                                   -- FK внутри агрегата, ставится после ниже (deferred)
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE flow_versions (
    id             uuid                     PRIMARY KEY DEFAULT gen_random_uuid(),
    flow_id        uuid                     NOT NULL REFERENCES flow(id) ON DELETE CASCADE,  -- FK ВНУТРИ агрегата
    version        integer                  NULL,                         -- монотонный № published; NULL у черновика
    status         flow_version_status_enum NOT NULL,
    definition     jsonb                    NOT NULL,                     -- ВЕСЬ граф одним документом (см. ниже)
    schema_version smallint                 NOT NULL DEFAULT 1,           -- версия ФОРМАТА JSON (app-миграции без DDL)
    content_hash   text                     NOT NULL,                     -- sha256(definition): дедуп/сравнение/аудит
    row_version    integer                  NOT NULL DEFAULT 0,           -- ОПТИМИСТИЧЕСКИЙ ЛОК черновика (перенос из jsonb-doc)
    created_at     timestamptz              NOT NULL DEFAULT now(),
    created_by     uuid                     NULL,
    published_at   timestamptz              NULL,
    CONSTRAINT uq_flow_version UNIQUE (flow_id, version)
);
-- Ровно один черновик на flow:
CREATE UNIQUE INDEX uq_flow_single_draft ON flow_versions (flow_id) WHERE status = 'draft';
-- Кросс-flow поиск по блокам (редкий) — GIN именно jsonb_path_ops (перенос из jsonb-doc):
CREATE INDEX ix_flow_versions_definition ON flow_versions USING gin (definition jsonb_path_ops);
-- Теперь можно замкнуть FK head→черновик (внутри агрегата):
ALTER TABLE flow ADD CONSTRAINT fk_flow_draft
    FOREIGN KEY (draft_version_id) REFERENCES flow_versions(id) DEFERRABLE INITIALLY DEFERRED;

-- Формат definition (валидируется ДОМЕНОМ, не БД):
-- {
--   "doc_schema_version": 1,
--   "entry_node_id": "...",
--   "triggers": [{ "id", "type": "start|text|callback|mini_app_result", "match": {...}, "entry_node_id" }],
--   "nodes": [{
--       "id", "type": "send_message|show_buttons|ask|condition|open_mini_app|save|http_request|custom_code",
--       "params": {...},                     -- тип-специфичная конфигурация блока (flow-blocks.md)
--       "pos": { "x": 120.0, "y": 340.0 },   -- координаты визуального редактора (перенос из Normalized, ADR-0007)
--       "buttons": [{ "id", "label", "action": "open_mini_app|callback|url|next", "target": {...} }],
--       "transitions": { "default": "node_id", "true": "...", "false": "..." },
--       "custom_code": { "code_id": "uuid", "version": 3 }   -- только для type=custom_code (BR-004)
--   }]
-- }

-- ============ Версии пользовательского Python-блока (BR-004) ============
CREATE TABLE custom_code_versions (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    code_id      uuid        NOT NULL,                                    -- логическая идентичность CustomCodeBlock
    version      integer     NOT NULL,
    source       text        NOT NULL,                                   -- исходник run(context)->dict; ДАННЫЕ, не исполняется в процессе
    content_hash text        NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   uuid        NULL,
    CONSTRAINT uq_custom_code_version UNIQUE (code_id, version)          -- строки ИММУТАБЕЛЬНЫ (только INSERT)
);
-- Исполняется ТОЛЬКО за CodeExecutorPort в песочнице (без БД/токенов/ФС/env/сети). Пин (code_id,version)
-- живёт в flow_versions.definition — фиксирует, какая версия исполнялась (воспроизводимость).

-- ============ Агрегат Session (durable-снапшот; горячий FSM — в Redis, §2) ============
CREATE TABLE session (
    id               uuid                PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id           uuid                NOT NULL,                        -- soft-ref
    flow_id          uuid                NOT NULL,                        -- soft-ref
    flow_version_id  uuid                NOT NULL,                        -- ПИН опубликованной версии (republish не ломает диалог)
    external_user_id text                NOT NULL,                        -- ПДн
    external_chat_id text                NULL,                            -- ПДн
    current_node_id  text                NOT NULL,                        -- id узла ВНУТРИ JSONB-графа (FK в БД невозможен)
    variables        jsonb               NOT NULL DEFAULT '{}',           -- FSM-контекст (потенциально ПДн)
    status           session_status_enum NOT NULL DEFAULT 'active',
    created_at       timestamptz         NOT NULL DEFAULT now(),
    updated_at       timestamptz         NOT NULL DEFAULT now(),
    last_event_at    timestamptz         NULL
);
-- «Ровно одна активная Session на (Bot, пользователь)» — defense-in-depth к доменному инварианту:
CREATE UNIQUE INDEX uq_session_active ON session (bot_id, external_user_id) WHERE status = 'active';
CREATE INDEX ix_session_bot ON session (bot_id);
-- ПДн: маскирование в логах, ретеншн и удаление по 152-ФЗ/GDPR — см. open questions ADR-0008.

-- ============ Журнал публикаций/lifecycle (перенос «аудита» hybrid) ============
CREATE TABLE publish_audit (
    id              bigserial           PRIMARY KEY,
    bot_id          uuid                NOT NULL,
    flow_id         uuid                NOT NULL,
    flow_version_id uuid                NULL,
    action          publish_action_enum NOT NULL,
    from_status     bot_status_enum     NULL,
    to_status       bot_status_enum     NULL,
    actor_id        uuid                NULL,
    created_at      timestamptz         NOT NULL DEFAULT now(),
    meta            jsonb               NULL                              -- доп. контекст; БЕЗ секретов/ПДн в открытом виде
);
-- Append-only. Откат = запись action='rollback' + переключение bot.published_flow_version_id на прошлую версию.

-- ============ CapabilityMatrix как ДАННЫЕ (перенос из Normalized; BR-005/BR-006) ============
CREATE TABLE capability_matrix (
    platform   platform_enum NOT NULL,
    capability text          NOT NULL,   -- тип Node/возможность: text, buttons, mini_app, payments, auth, http_request, custom_code…
    available  boolean       NOT NULL DEFAULT true,
    PRIMARY KEY (platform, capability)
);
-- Seed-данные (не пользовательские). BR-006 проверяется данными/JOIN'ом в домене при публикации Flow, НЕ через if platform==.
```

**Опциональный webhook_idempotency в Postgres — не заводим.** Идемпотентность — только Redis (ADR-0004), `IncomingEvent` транзиентен и агрегатом не персистится. Таблица в PG появилась бы лишь при требовании долговременного аудита приёма — вне текущего решения.

---

## 2. Что в Redis 7 (форматы ключей и TTL)

| Назначение | Ключ | Тип / операция | Значение | TTL |
|---|---|---|---|---|
| Горячий runtime-FSM Session | `session:{bot_id}:{external_user_id}` | HASH | `{session_id, flow_version_id, current_node_id, variables}` | idle-TTL `SESSION_IDLE_TTL` (дефолт 3600 c, конфиг), скользящий при активности |
| Блокировка единственности активной сессии | `session:lock:{bot_id}:{external_user_id}` | `SET … NX PX` | `session_id` | короткий, на время обработки апдейта (напр. 10 c) |
| Идемпотентность вебхука (ADR-0004) | `idemp:{platform}:{bot_id}:{update_id}` | `SET key 1 NX EX <ttl>` | маркер | `WEBHOOK_IDEMPOTENCY_TTL` = 86400 c (24 ч) |

Правила:
- **Session:** источник правды для восстановления — Postgres `session`. Redis — скорость + оперативная блокировка. Запись — **write-through**: каждый зафиксированный шаг движка пишется в Redis и снапшотится в PG в той же логической транзакции агрегата. Промах/вытеснение Redis → регидрация из `session`. Единственность активной сессии страхуется в двух местах: partial-unique в PG (авторитет) + lock-ключ в Redis (горячий путь).
- **Идемпотентность:** первый приём ставит ключ через `SET NX` и запускает pipeline `приём → нормализация → идемпотентность → запуск`; повтор с тем же `{platform, bot_id, update_id}` отбрасывается. TTL 24 ч перекрывает окна ретраев обеих платформ (у MAX авто-отписка после 8 ч без 200 OK). Точный источник `update_id` — деталь адаптера (`infrastructure/platforms/*/webhook.py`).
- ПДн (`external_user_id`, `variables`) в Redis живут не дольше idle-TTL; в логи/метрики значения ключей не попадают.

---

## 3. Граница токенов (token vault)

- Секрет токена **никогда** не попадает в основную БД. В `bot` лежит только `token_vault_ref` — непрозрачный хэндл/путь/key-id записи в token vault (например `secret/bots/{bot_id}` или `vault_secret_id`), **не значение**.
- Само значение живёт исключительно за портом **`TokenVaultPort`** (реализация в `infrastructure/`). Токен не пишется ни в одну колонку Postgres, ни в JSONB `definition`, ни в логи/метрики/тексты ошибок.
- При `Bot.publish` валидность токена проверяется через vault + платформу (BR-001); результат проверки не персистится как секрет. Значение берётся из vault только в момент вызова платформенного API (для MAX — в заголовке `Authorization`, ответственность `MaxBotAdapter`).
- **init data mini app** — такой же секрет (BR-007): не хранится вообще, валидируется по подписи на backend на лету.
- Конкретный бэкенд vault (HashiCorp Vault / SOPS / секреты CI) — не выбран, `TOKEN_VAULT_URL` (не секрет) / `TOKEN_VAULT_TOKEN` (секрет) условны — open question ADR-0008.

**Почему только ссылка:** секрет вне основной БД снижает площадь утечки (дампы/бэкапы/логи PG не содержат токенов), ротация и отзыв — операция vault, не миграция данных; схема хранения токена не связывается с реляционной схемой.

---

## 4. Порты и методы (Python Protocol)

Порты живут в `application/ports/` (или `domain/ports/`), реализуются в `infrastructure/db/`. Аргументы/возврат — доменные объекты и id, **не** ORM-модели.

```python
from typing import Protocol
from uuid import UUID
from domain.flow.entities import Flow
from domain.flow.version import FlowVersion          # published/draft снапшот как доменный объект
from domain.session.entities import Session


class FlowRepository(Protocol):
    """Хранение и чтение сценариев (Flow) — глоссарий. Агрегат читается/пишется ЦЕЛИКОМ."""

    async def get_draft(self, flow_id: UUID) -> Flow | None:
        """flow(head) + flow_versions(status='draft').definition → десериализация агрегата целиком."""

    async def save_draft(self, flow: Flow, *, expected_row_version: int) -> int:
        """Upsert единственной draft-строки in-place с оптимистическим локом (row_version).
        Возвращает новый row_version; при конфликте версии — поднимает ConcurrencyError."""

    async def publish(self, flow_id: UUID, *, actor_id: UUID | None) -> FlowVersion:
        """Заморозка черновика в новую ИММУТАБЕЛЬНУЮ published-строку (version=next),
        запись publish_audit. Инварианты BR-001/BR-006 проверяет домен ДО вызова."""

    async def get_published(self, bot_id: UUID) -> FlowVersion | None:
        """Загрузка исполняемой версии для рантайма по bot.published_flow_version_id — один SELECT."""

    async def load_version(self, flow_version_id: UUID) -> FlowVersion:
        """Иммутабельный снапшот для конкретной активной Session (по session.flow_version_id)."""

    async def list_versions(self, flow_id: UUID) -> list[FlowVersion]:
        """История версий (+ аудит) для UI/отката."""


class SessionRepository(Protocol):
    """Хранение состояния пользователя (Session) — глоссарий. Redis(hot) + Postgres(durable)."""

    async def find_active(self, bot_id: UUID, external_user_id: str) -> Session | None:
        """Redis (горячий FSM) с фолбэком/регидрацией из PG session."""

    async def start(self, session: Session) -> Session:
        """INSERT session (partial-unique active страхует единственность) + Redis hash/lock.
        session.flow_version_id пинит версию сценария."""

    async def save(self, session: Session) -> None:
        """Write-through: Redis (current_node_id + variables) + durable-снапшот в PG session."""

    async def finish(self, session_id: UUID) -> None:
        """status → 'completed', снятие Redis-ключа/лока."""

    async def expire(self, session_id: UUID) -> None:
        """status → 'expired' (по TTL-вытеснению)."""
```

**Что схема обязана поддержать под эти сигнатуры:**
- `get_draft`/`save_draft` ⇐ `flow.draft_version_id` + partial-unique одного черновика + `row_version` (оптимистический лок).
- `publish` ⇐ `UNIQUE(flow_id, version)`, иммутабельность published-строк (запрет UPDATE на уровне репозитория), `publish_audit`.
- `get_published` ⇐ `bot.published_flow_version_id` (прямой указатель, одна строка).
- `load_version` ⇐ append-only `flow_versions` (версия по `session.flow_version_id` всегда существует).
- `find_active`/`start` ⇐ partial-unique `uq_session_active` + пин `flow_version_id`.

**Расхождение (в ADR-0008):** `BotRepository`/`MiniAppRepository` в глоссарии **не заведены**, хотя агрегат Bot требует своего порта (таблицы `bot` + `mini_app` + `published_flow_version_id` + `publish_audit`). Кандидатная сигнатура: `BotRepository.get/save/publish/pause/resume`.

---

## 5. Эскиз SQLAlchemy 2 (async) + маппинг домен↔ORM

**Домен НЕ наследует `Base`.** Доменные сущности — обычные (frozen) dataclass'ы в `domain/`, без импорта SQLAlchemy. ORM-модели живут в `infrastructure/db/models.py`, перевод домен↔ORM — в `infrastructure/db/mappers.py` (DTO/маппер на границе). Репозитории (`infrastructure/db/repositories.py`) реализуют порты из §4.

```python
# infrastructure/db/models.py  — ТОЛЬКО инфраструктура (import-linter не пускает это в domain/application)
from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Integer, SmallInteger, ForeignKey, Enum as SAEnum, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from domain.flow.enums import FlowVersionStatus       # доменный enum переиспользуем как values_callable
from domain.session.enums import SessionStatus


class Base(DeclarativeBase):
    pass


class FlowVersionModel(Base):
    __tablename__ = "flow_versions"

    id:             Mapped[UUID]     = mapped_column(PGUUID(as_uuid=True), primary_key=True,
                                                     server_default=text("gen_random_uuid()"))
    flow_id:        Mapped[UUID]     = mapped_column(PGUUID(as_uuid=True), ForeignKey("flow.id", ondelete="CASCADE"))
    version:        Mapped[int | None] = mapped_column(Integer, nullable=True)
    status:         Mapped[FlowVersionStatus] = mapped_column(
                        SAEnum(FlowVersionStatus, name="flow_version_status_enum",
                               values_callable=lambda e: [m.value for m in e]))
    definition:     Mapped[dict]     = mapped_column(JSONB)                 # весь граф одним документом
    schema_version: Mapped[int]      = mapped_column(SmallInteger, default=1)
    content_hash:   Mapped[str]      = mapped_column(String)
    row_version:    Mapped[int]      = mapped_column(Integer, default=0)    # оптимистический лок
    created_at:     Mapped[datetime] = mapped_column(server_default=text("now()"))
    published_at:   Mapped[datetime | None]


class SessionModel(Base):
    __tablename__ = "session"

    id:               Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True,
                                                   server_default=text("gen_random_uuid()"))
    bot_id:           Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))    # soft-ref, без ForeignKey
    flow_id:          Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    flow_version_id:  Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))    # пин версии, soft-ref
    external_user_id: Mapped[str]  = mapped_column(String)
    external_chat_id: Mapped[str | None]
    current_node_id:  Mapped[str]  = mapped_column(String)
    variables:        Mapped[dict] = mapped_column(JSONB, default=dict)
    status:           Mapped[SessionStatus] = mapped_column(
                          SAEnum(SessionStatus, name="session_status_enum",
                                 values_callable=lambda e: [m.value for m in e]))
    created_at:       Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at:       Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_event_at:    Mapped[datetime | None]
```

```python
# infrastructure/db/mappers.py  — DTO/маппер на границе: ORM <-> домен
from domain.session.entities import Session
from infrastructure.db.models import SessionModel


def session_to_domain(row: SessionModel) -> Session:
    return Session(                                   # домен — чистый dataclass, без Base
        id=row.id, bot_id=row.bot_id, flow_id=row.flow_id,
        flow_version_id=row.flow_version_id,
        external_user_id=row.external_user_id, external_chat_id=row.external_chat_id,
        current_node_id=row.current_node_id, variables=dict(row.variables),
        status=row.status,
    )


def session_to_row(s: Session) -> SessionModel:
    return SessionModel(
        id=s.id, bot_id=s.bot_id, flow_id=s.flow_id, flow_version_id=s.flow_version_id,
        external_user_id=s.external_user_id, external_chat_id=s.external_chat_id,
        current_node_id=s.current_node_id, variables=s.variables, status=s.status,
    )
```

**Правила маппинга:**
- Один агрегат ⇄ одна логическая единица. `Flow` собирается из `flow_versions.definition` **целиком** без join'ов по node/trigger/button — граф уже документ. Обратно — `flow.to_document()` в домене отдаёт dict, маппер кладёт в `definition`.
- Enum'ы блоков (Node/Trigger/Button.action) — **внутри** JSONB, не DB-enum; их валидирует домен. DB-enum — только колоночные `platform/bot_status/flow_version_status/session_status`.
- Кросс-агрегатные ссылки (`bot_id`, `flow_id`, `flow_version_id`) — `PGUUID` без `ForeignKey` (граница агрегата).
- Домен НЕ импортирует `infrastructure.db.*`; маппер импортирует домен — направление зависимостей соблюдено, `lint-imports` зелёный.

---

## 6. Миграции (Alembic)

**Инструмент:** Alembic (разумный дефолт под SQLAlchemy 2 async; командой формально не подтверждён — `policy_db_migrations: ask`, вынесено в ADR-0008).

**Структура:**
```
migrations/
  env.py            # async engine из DATABASE_URL; target_metadata = Base.metadata
  script.py.mako
  versions/
    0001_initial_schema.py
alembic.ini
```

**Первая миграция `0001_initial_schema`** (порядок операций):
1. `CREATE TYPE` для 5 enum'ов (`platform`, `bot_status`, `flow_version_status`, `session`, `publish_action`).
2. Таблицы: `bot`, `mini_app`, `flow`, `flow_versions`, `custom_code_versions`, `session`, `publish_audit`, `capability_matrix` (8 таблиц).
3. Индексы/констрейнты: partial-unique `uq_flow_single_draft`, GIN `ix_flow_versions_definition (jsonb_path_ops)`, deferred FK `fk_flow_draft`, partial-unique `uq_session_active`, CHECK `ck_mini_app_https`.
4. Seed `capability_matrix` (data-миграция в `upgrade()`).
`downgrade()` — зеркально (drop таблиц → drop типов).

**Эволюция без DDL — ключевое преимущество:** новые типы Node и поля `params` схему БД **не трогают** (живут в `definition`). Формат самого документа эволюционирует через `schema_version` + **прикладная** data-миграция (backfill-скрипт или ленивый upcast при чтении в репозитории) — это **вне Alembic**, со своими тестами. Расширение Platform (VK/WhatsApp) — неразрушающий `ALTER TYPE platform_enum ADD VALUE` отдельной миграцией (в PG16 безопасно).

**CI-гейт:**
- Джоба поднимает **testcontainers Postgres 16** → `alembic upgrade head` → `alembic downgrade base` → снова `upgrade head` (проверка обратимости).
- **Drift-check:** `alembic check` (autogenerate против `Base.metadata` даёт пустой diff) — модель и миграции не расходятся.
- **Инвариант «битый definition нельзя опубликовать»** (перенос интента композитного FK из Normalized): CI-тест + JSON-schema-валидация `definition` с учётом `schema_version` — обязательный гейт публикации.
- Autogenerate ревьюится вручную (partial-индексы, GIN `jsonb_path_ops`, deferred FK autogenerate воспроизводит неточно). Разрушительные операции — только с подтверждением (`policy_db_migrations: ask`). Агент к stage/prod БД не подключается (`policy_prod_commands: never`).

---

## 7. Локальное подключение (docker-compose + env)

```yaml
# docker-compose.yml — эскиз
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: meta_bot
      POSTGRES_PASSWORD: meta_bot
      POSTGRES_DB: meta_bot
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U meta_bot -d meta_bot"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

```dotenv
# .env.example — эскиз (реальный .env в .gitignore; секреты не коммитим)
APP_ENV=local                                                          # local|dev|stage|prod
DATABASE_URL=postgresql+asyncpg://meta_bot:meta_bot@localhost:5432/meta_bot   # драйвер asyncpg
REDIS_URL=redis://localhost:6379/0                                     # в prod содержит пароль → секрет
SESSION_IDLE_TTL=3600                                                  # c, idle-TTL горячей Session в Redis
WEBHOOK_IDEMPOTENCY_TTL=86400                                          # c, 24 ч (ADR-0004)
TOKEN_VAULT_URL=http://localhost:8200                                  # адрес vault (не секрет); бэкенд не выбран
TOKEN_VAULT_TOKEN=                                                     # СЕКРЕТ — только окружение, не репозиторий
ADMIN_API_SECRET=                                                      # СЕКРЕТ
```

Поднятие: `docker compose up -d postgres redis` → `alembic upgrade head`. Реальный vault локально для прогона не нужен (заглушка `TokenVaultPort`). Строки подключения PG/Redis — секреты; в базу знаний и логи не кладём.

---

## 8. Порядок сборки вертикального среза (чек-лист)

1. [ ] **Домен `Flow`/`FlowVersion`** (`domain/flow/`): сущности + enum'ы (Node/Trigger/Button.action как доменные) + инварианты (≥1 Trigger BR-001, достижимость Node, нет висячих переходов, `to_document()`/`from_document()`). Без SQLAlchemy. Юнит-тесты инвариантов.
2. [ ] **Домен `Session`** (`domain/session/`): FSM-сущность + инвариант «одна активная на (Bot, user)». Юнит-тесты.
3. [ ] **Порты** (`application/ports/`): `FlowRepository`, `SessionRepository` (§4) как Protocol. `lint-imports` зелёный.
4. [ ] **JSON-schema `definition`** + доменный валидатор (гейт публикации) — интент композитного FK.
5. [ ] **`infrastructure/db/models.py`** (§5): `Base` + ORM-модели. Изолированы от домена — проверить `lint-imports`.
6. [ ] **Alembic `0001_initial_schema`** (§6): enum'ы + 8 таблиц + индексы + seed `capability_matrix`.
7. [ ] **`infrastructure/db/mappers.py`**: домен↔ORM DTO-маппер (домен не наследует `Base`).
8. [ ] **`infrastructure/db/repositories.py`**: реализации `FlowRepository`/`SessionRepository` (upsert head + INSERT версии в одной транзакции; write-through Redis+PG для Session).
9. [ ] **Первый интеграционный тест против testcontainers (Postgres 16 + Redis 7):**
   - save_draft → publish → get_published: агрегат читается/пишется целиком одной транзакцией, published-версия иммутабельна;
   - оптимистический лок: конкурентный `save_draft` со старым `row_version` → `ConcurrencyError`;
   - partial-unique: вторая активная Session на ту же (bot, user) → нарушение;
   - `find_active`: Redis-hit и фолбэк-регидрация из PG.
10. [ ] **CI:** `lint-imports` + `alembic upgrade/downgrade/check` + интеграционные тесты на testcontainers. Обновить memory-bank (business-rules/glossary/tech-stack) в том же PR.

Направление сборки строго снизу вверх по зависимостям: **домен → порты → infrastructure/db → интеграционный тест**. Ни на одном шаге БД не «протекает» вверх.

---

## 9. Черновик ADR-0008

```markdown
---
status: draft
version: "1.0"
updated: 2026-07-08
verified_commit: ""
owner: ""
decision_status: proposed
---

# ADR-0008: Модель хранения (persistence)
```

> Черновик на ратификацию командой. `accepted` ставит владелец раздела.

## Контекст

Нужно зафиксировать физическую модель хранения трёх корней агрегата (Bot, Flow,
Session) на стеке PostgreSQL 16 + SQLAlchemy 2 (async) + Redis 7, не нарушив
строгий Clean Architecture (БД — деталь инфраструктуры за портами; домен не знает
про SQLAlchemy/Redis). Силы, действующие на решение:

- Продукт — **конструктор сценариев с жизненным циклом Draft→Published→Paused**;
  версионирование Flow и чистая загрузка published-версии рантаймом — ключевые
  фичи, а не второстепенные (BR-001).
- Агрегат Flow по DDD грузится/сохраняется **целиком одной транзакцией**;
  инварианты графа — код домена, не БД-констрейнты.
- Секреты (Token, init data) — вне основной БД (BR-004/BR-007, security).
- Различия платформ — данными, не ветвлением (BR-005/BR-006).
- Если не решить сейчас: расходятся tech-stack ↔ AGENTS по границе Redis/PG для
  Session; в глоссарии нет `BotRepository`; версионирование Flow не описано —
  это блокирует первый вертикальный срез бэка.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. Оставить как есть (не фиксировать модель) | Ничего не переделывать сейчас | Нельзя собрать срез; расхождения tech-stack↔AGENTS и дыры (BotRepository, версии Flow) остаются |
| 2. jsonb-doc: Flow = JSONB-документ, head+версии | Самый простой (6 таблиц, одна строка на чтение/запись); эволюция без DDL; чистые границы | Нет журнала аудита публикаций; Draft/Published без зрелой модели; риск потери правок без оптимистического лока |
| 3. Normalized: граф Flow по таблицам node/transition/trigger/button с FK | Реляционные гарантии графа; SQL-аналитика по блокам; частичный UPDATE узла | Дорогой снапшот published-версии (глубокое копирование); тяжёлый ORM-маппинг; жёсткая эволюция (ALTER TYPE/DDL); соблазн валидации в БД-триггерах |
| 4. **Hybrid-versioned (выбран): flow_versions (JSONB-снапшот + номер) + указатель published, Draft отдельно от Published, Redis-runtime, token vault** | Чистое разделение Draft/Published; иммутабельные снапшоты + `publish_audit` + мгновенный откат; пиннинг активных Session на версию; чтение published одной строкой; эволюция графа без DDL; секреты вне БД | Дублирование графа между версиями (рост объёма); write-amplification больших Flow; целостность графа — только домен; двойное хранилище Session требует согласования; upcast формата — вне Alembic |

## Решение

Принимаем **Hybrid-versioned** как модель хранения, усиленную переносами от
проигравших стратегий:

- **Flow** — тонкий head (`flow`) + иммутабельные версии (`flow_versions.definition`
  JSONB, весь граф одним документом). Черновик — единственная mutable-строка
  `status='draft'` (partial-unique) с **оптимистическим локом `row_version`**
  (перенос из jsonb-doc). Публикация замораживает черновик в новую published-строку
  (`version=next`) и переводит указатель на неё; `publish_audit` — append-only журнал
  lifecycle; откат = переключение указателя.
- **Указатель published живёт на `bot.published_flow_version_id`** (удобно рантайму:
  исполняемая версия — один прямой SELECT). Это осознанная развилка владения фактом
  «какая версия опубликована»: по DDD published-ность концептуально принадлежит Flow,
  но SSoT размещаем на Bot ради загрузки рантаймом (см. риски).
- **Session** — durable-снапшот в PG `session` (авторитет единственности —
  partial-unique `WHERE status='active'`, пин `flow_version_id`); горячий FSM и
  идемпотентность вебхуков — в Redis (write-through, ключи и TTL — §2 пакета).
  Это ратифицирует границу Redis↔PG (расхождение tech-stack↔AGENTS).
- **Токен** — только `token_vault_ref` в `bot`, значение — за `TokenVaultPort`.
- **CapabilityMatrix — данными** (таблица `capability_matrix`, BR-006 через
  данные/JOIN, не `if platform==`) — перенос из Normalized.
- **Enum'ы блоков** (Node/Trigger/Button.action) — внутри JSONB, валидирует домен;
  DB-enum только колоночные (platform/bot_status/flow_version_status/session).
- **Защита в глубину:** CHECK HTTPS на `mini_app.url`, JSON-schema/CI-гейт «битый
  `definition` нельзя опубликовать» (интент композитного FK из Normalized),
  координаты редактора `pos` в узлах JSONB (ADR-0007), GIN `jsonb_path_ops`;
  авторитет всех инвариантов — домен.
- Граница решения: только `infrastructure/` (модели/мапперы/репозитории/миграции)
  + порты в `application/ports`. Домен и application про БД не знают.

Решающий аргумент: критерии «версионирование Draft/Published» и «чистая загрузка
published рантаймом» — определяющие для продукта-конструктора, и там Hybrid
доминирует; простота jsonb-doc возвращается переносом его лёгких механизмов.

## Последствия

**Положительные:**
- Чистое разделение Draft/Published: правка черновика не трогает прод; рантайм
  исполняет иммутабельный снапшот; активные диалоги переживают републикацию (пин).
- Полный аудит и мгновенный откат (`flow_versions` + `publish_audit`).
- Агрегат Flow читается/пишется одним документом в одной транзакции — совпадает с
  DDD-границей; меньше таблиц и площадь протечки ORM.
- Эволюция графа без DDL (новые блоки/params в JSONB; формат — через `schema_version`).
- Секреты вне основной БД; ПДн локализованы в `session` (проще ретеншн по 152-ФЗ/GDPR).
- BR-005/BR-006 выражены данными (`capability_matrix`), а не ветвлением.

**Отрицательные:**
- Целостность графа не гарантируется реляционно — только домен + JSON-schema/CI-гейт.
- Write-amplification: правка = перезапись всего документа; большие Flow → крупные
  строки/TOAST; частичный UPDATE узла невозможен (принятый риск, митигация — лок).
- Дублирование графа между версиями → рост объёма; нужна политика архивации
  (`status='archived'`) старых версий.
- Двойное хранилище Session (Redis+PG) требует write-through/регидрации и двух точек
  согласования единственности (partial-unique в PG + lock в Redis).
- Upcast формата JSONB (`schema_version`) — отдельный инструментарий вне Alembic.

**Риски:**
- Обход домена может записать «битый» `definition` → **сигнал/митигация:** JSON-schema
  + обязательный CI-тест как гейт публикации; падение гейта заметно в CI.
- Указатель published на Bot vs Flow — концептуальная развилка владения; если модель
  прав/несколько ботов на один Flow изменит владение, потребуется пересмотр
  (**срок пересмотра:** при вводе multi-tenancy/owner_id).
- Eventual consistency Bot↔Flow↔Session (ссылки по id, без outbox) → окна
  рассинхронизации указателей; **сигнал:** рассинхрон `published_flow_version_id`;
  митигация — ввести outbox/сагу при необходимости.
- Alembic не подтверждён командой (`policy_db_migrations: ask`).

**Открытые вопросы (наследуются, кандидаты в отдельные ADR):**
- Порт `BotRepository`/`MiniAppRepository` не заведён в глоссарии.
- `owner_id`/RBAC/multi-tenancy не зафиксированы.
- ПДн в `session.variables`/`external_*`: маскирование, сроки хранения, удаление.
- Точный состав ключа идемпотентности (`update_id`) и TTL (ADR-0004).
- Бэкенд token vault (Vault/SOPS/секреты CI).
- Хранение версий custom_code: PG-таблица vs `FileStoragePort`.
- Alembic как инструмент миграций — ратификация.
- Аналитика по блокам — отдельный read-model/materialized view (CQRS), а не
  нормализация write-модели.

## Ссылки

- `../architecture/overview.md` — слои и направление зависимостей
- `../architecture/patterns.md` — capability matrix, запрет ветвления по платформе
- `../domain/domain-model.md`, `../domain/glossary.md` — агрегаты и порты
- `../domain/business-rules.md` — BR-001..007
- `0003-flow-engine-blocks-and-sandbox.md` — блоки как данные, песочница (BR-004)
- `0004-webhook-platform-integration.md` — идемпотентность вебхуков в Redis
- `0005-capability-matrix.md` — CapabilityMatrix
- `0007-visual-flow-editor.md` — координаты узлов
- `../architecture/security.md` — token vault, TokenVaultPort
- `../architecture/tech-stack.md`, `../ops/configuration.md` — PG16/Redis7, DATABASE_URL/REDIS_URL

---

**Примечание по процессу:** ADR-0008 создан автономно **только** как `decision_status: proposed`; статус `accepted` проставляет владелец раздела (governance). При заведении файла — добавить строку в реестр `memory-bank/decisions/README.md` и прогнать `python scripts/validate_memory_bank.py`. `version`/`updated` во frontmatter вручную не проставлять (автоматика). Файл для создания: `memory-bank/decisions/0008-persistence-model.md`.