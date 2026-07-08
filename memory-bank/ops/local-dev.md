---
status: active
version: "1.2"
updated: 2026-07-09
verified_commit: ""
owner: ""
---

# Локальный запуск meta-bot-core

Цель: разработчик или агент поднимает конструктор с нуля на чистой машине,
не задавая вопросов команде. Переменные окружения — в
[configuration.md](configuration.md), версии стека — в
[../architecture/tech-stack.md](../architecture/tech-stack.md), слои и границы —
в [../architecture/overview.md](../architecture/overview.md).

## Предусловия

Инструменты, без которых проект не поднимется. Точные версии — из
[../architecture/tech-stack.md](../architecture/tech-stack.md).

- [ ] **uv** (менеджер зависимостей и версий Python): `winget install astral-sh.uv`.
      Python 3.14 uv поставит сам по `.python-version` — отдельная установка не нужна.
- [ ] Lock-файл — `uv.lock` (решение 2026-07-08); зависимости ставятся `uv sync`,
      команды запускаются `uv run X`.
- [ ] Docker Desktop + `docker compose` — для локальных PostgreSQL 16 и Redis 7
      (Docker Desktop ≥ 4.30). Проверка: `docker compose version`.
- [ ] `src/` в `PYTHONPATH` (корневые пакеты слоёв — `domain`/`application`/
      `infrastructure`/`presentation`); задаётся менеджером зависимостей либо
      `export PYTHONPATH=src`.
- [ ] Доступ к git-репозиторию meta-bot-core. Token vault и реальные токены ботов
      для локального прогона **не нужны** — секреты в базу знаний и в код не кладём
      ([../architecture/security.md](../architecture/security.md)).
- [ ] (Опционально) туннель для приёма вебхуков: `ngrok` или `cloudflared` —
      см. раздел «Приём вебхуков локально».

## Шаги запуска с нуля

1. Клонировать репозиторий и перейти в корень.
2. Создать локальную конфигурацию: скопировать `.env.example` → `.env` и заполнить
   значения по [configuration.md](configuration.md) (`.env` — в `.gitignore`,
   в базу знаний и логи секреты не попадают).
3. Поднять инфраструктуру в контейнерах: PostgreSQL 16 (хранилище `Bot`/`Flow`/
   `Session`) и Redis 7 (runtime-состояние FSM `Session` и идемпотентность вебхуков).
4. Установить зависимости из lock-файла.
5. Применить миграции БД — **Alembic** (`alembic.ini` + `migrations/`; при
   запуске через compose команда api применяет их сама). Создание миграций и
   любые разрушительные операции — под политикой `policy_db_migrations`.
6. Запустить FastAPI-приложение (presentation: admin API конструктора +
   webhook-роуты) через uvicorn. Composition root — `src/main.py`.

Пример:

```bash
git clone <repo-url-meta-bot-core> && cd meta-bot-core
cp .env.example .env                # опционально: без .env compose берёт dev-дефолты
docker compose up -d --build       # api (с миграциями) + postgres:16 + redis:7
# либо только инфраструктура + API на хосте:
docker compose up -d postgres redis
uv sync                            # окружение из uv.lock (Python 3.14 поставит uv)
uv run alembic upgrade head        # Postgres проброшен на localhost:5433
uv run uvicorn main:app --reload --port 8000
```

## Приём вебхуков локально

В production обновления принимаются **только через webhook**
([ADR-0004](../decisions/0004-webhook-platform-integration.md)); роуты —
`/webhooks/telegram/{bot_id}` и `/webhooks/max/{bot_id}` (→ `IncomingEvent`).
Локально есть два режима:

- **Long polling — только для отладки.** Допустим для быстрой локальной проверки
  без публичного адреса; в prod не используется. Учти: у Telegram включённый
  webhook отключает `getUpdates` — держи один режим за раз.
- **Туннель для webhook (ближе к prod).** Публичный HTTPS-адрес до локального
  uvicorn через `ngrok`/`cloudflared`, затем регистрация webhook у платформы на
  `https://<tunnel>/webhooks/telegram/{bot_id}`. Telegram принимает webhook только
  на портах 443/80/88/8443 — туннель по умолчанию отдаёт 443, что подходит.
  Для MAX запросы идут на `platform-api2.max.ru` (миграция с `platform-api.max.ru`
  до 19.07.2026), токен — в заголовке `Authorization`, не в query.

Регистрация webhook и отправка сообщений живым ботам — это **реальные вызовы Bot
API** Telegram/MAX: закрыты флагом `policy_external_api_calls` (`ask`) в
[../_meta/policy.md](../_meta/policy.md). Агент выполняет их только по явной просьбе
человека в текущей сессии; молча — никогда. Токены и init-данные mini app —
секреты, не логировать ([../architecture/security.md](../architecture/security.md)).

## Локальные проверки перед коммитом

Гоняются локально до пуша; те же проверки — в pre-commit и CI. Порядок:

```bash
PYTHONPATH=src uv run lint-imports          # границы слоёв (import-linter, .importlinter)
uv run ruff format src tests migrations && uv run ruff check src tests migrations
uv run mypy                                 # типизация, режим strict
uv run pytest -m unit                       # быстрые unit-тесты (domain + application)
python scripts/validate_memory_bank.py      # валидность базы знаний (если правил memory-bank)
```

- `lint-imports` обязателен **до и после** правки `src/`: контракт — корневой
  [../../.importlinter](../../.importlinter), джоба `arch-lint`
  ([../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)).
  Красный `lint-imports` = красная сборка. Протечку слоя чинят разворотом
  зависимости, а не заглушкой ([../../.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md));
  ослабление контракта закрыто политикой `policy_bypass_arch_lint`.
- `pytest -m integration` требует Docker (testcontainers: Postgres 16, Redis 7);
  уровни и пороги покрытия — [../architecture/testing-strategy.md](../architecture/testing-strategy.md).
- Правил memory-bank не касался — `validate_memory_bank.py` можно пропустить.

## Очистка локальных артефактов

Инструменты складывают кеши в корень (`.mypy_cache`, `.ruff_cache`, `.pytest_cache`,
`.import_linter_cache`, `.uv-cache`, `__pycache__`, `*.egg-info`, `.coverage`). В git
и Docker они не входят (`.gitignore`, `.dockerignore`) и скрыты из дерева VSCode
(`.vscode/settings.json`). Сбросить их с диска — одной командой:

```bash
python scripts/clean.py            # кеши сборки/тестов/линтеров + __pycache__ + dist
python scripts/clean.py --deep     # плюс координационный кеш ruflo (.swarm, ruvector.db)
python scripts/clean.py --dry-run  # показать, что удалит, ничего не трогая
```

Рабочее окружение (`.venv/`, `node_modules/`) и секреты (`.env`) скрипт не трогает —
всё удаляемое пересоздаётся инструментами. Кеш uv держится в общем кеше пользователя,
а не в проекте (`[tool.uv]` в `pyproject.toml` без `cache-dir`).

## Как проверить, что всё поднялось

- [ ] Healthcheck отвечает: `GET /healthchecks/` → 200 (сервис/версия/uptime);
      `GET /healthchecks/services/` → статусы Postgres и Redis.
- [ ] Сквозной путь MVP: вебхук `POST /webhooks/telegram/{bot_id}` принимается и
      порождает `IncomingEvent`; сценарий на `/start` отдаёт ответ (`SendMessageUseCase`).
- [ ] Проверки проходят локально: `uv run pytest -m unit`
      (уровни — [../architecture/testing-strategy.md](../architecture/testing-strategy.md)).
- [ ] В логах при старте нет ERROR (куда смотреть — [observability.md](observability.md)).

## Типовые проблемы запуска

Дополняй таблицу при каждой новой проблеме, отнявшей > 15 минут.

| Симптом | Причина | Решение |
|---|---|---|
| `connection refused` к БД/Redis при старте | Контейнер ещё не готов, приложение стартовало раньше | Дождаться healthy: `docker compose ps`; перезапустить uvicorn |
| `ModuleNotFoundError: domain/application/...` | `src/` не в `PYTHONPATH` | `export PYTHONPATH=src` или запуск через `uv run` (editable-установка) |
| Порт 5432 занят другим Postgres | На машине уже работает чужой Postgres | Наш проброшен на `localhost:5433` (compose), менять ничего не нужно |
| Telegram: webhook не регистрируется / бот не отвечает через туннель | Публичный порт не 443/80/88/8443, либо активен long polling (`getUpdates` конфликтует с webhook) | Использовать туннель на 443; отключить long polling, оставить один режим |
| MAX: 401/404 на запросах Bot API | Обращение к старому `platform-api.max.ru` или токен в query | Перевести на `platform-api2.max.ru`, токен — в заголовке `Authorization` |
| `lint-imports` красный после правки `src/` | Протечка слоя (импорт наружу / между платформами) | Чинить разворотом зависимости за порт, не глушить линтер ([../../.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md)) |

## Правила

- **Ничего разрушительного без подтверждения.** Локально (окружение `local`)
  разрешены эксперименты, но создание/применение миграций и удаление файлов —
  под флагами `policy_db_migrations` и `policy_file_delete` (`ask`) в
  [../_meta/policy.md](../_meta/policy.md); stage/prod агент локально не трогает
  ([environments.md](environments.md)).
- Реальные вызовы Telegram/MAX (webhook, отправка сообщений) — `policy_external_api_calls`
  (`ask`), только по явной просьбе человека.

## Вопросы заполняющему

- Что нужно от «голой» ОС до первого успешного запуска? Пройди сам и запиши.
- Есть ли шаги, различающиеся по ОС (Windows/macOS/Linux)? Отметь явно.
- Что из инфраструктуры можно замокать локально, а что обязательно живое?
