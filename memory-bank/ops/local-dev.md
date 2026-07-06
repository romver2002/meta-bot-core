---
status: active
version: "1.0"
updated: 2026-07-06
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

- [ ] Python 3.12 (единый async-рантайм backend). Windows: `winget install Python.Python.3.12`
      либо через `pyenv`. Проверка: `python --version` → 3.12.x.
- [ ] Менеджер зависимостей и lock-файл: **poetry** или **uv** — выбор команды
      (`poetry.lock` / `uv.lock`), уточнить у команды. Примеры ниже даны для poetry;
      для uv замените `poetry install` → `uv sync`, `poetry run X` → `uv run X`.
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
5. Применить миграции БД. Инструмент миграций (Alembic при SQLAlchemy 2 —
   разумный дефолт) уточнить у команды. Создание миграций и любые разрушительные
   операции — под политикой `policy_db_migrations` (см. «Правила» ниже).
6. Запустить FastAPI-приложение (presentation: admin API конструктора +
   webhook-роуты) через uvicorn. Composition root — `src/main.py`.

Пример (poetry; для uv — эквиваленты из «Предусловий»):

```bash
git clone <repo-url-meta-bot-core> && cd meta-bot-core
cp .env.example .env                       # заполнить по configuration.md
docker compose up -d postgres redis        # образы postgres:16, redis:7 — точные теги уточнить у команды
poetry install                             # из poetry.lock (или: uv sync)
poetry run alembic upgrade head            # применить миграции (инструмент уточнить у команды)
poetry run uvicorn main:app --reload --port 8000   # src/ в PYTHONPATH → http://localhost:8000
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
lint-imports                              # границы слоёв (import-linter, контракт .importlinter)
poetry run ruff format . && poetry run ruff check .   # формат + линт
poetry run mypy .                         # типизация, режим strict
poetry run pytest -m unit                 # быстрые unit-тесты (domain + application)
python scripts/validate_memory_bank.py    # валидность базы знаний (если правил memory-bank)
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

## Как проверить, что всё поднялось

- [ ] Healthcheck-эндпоинт отвечает: `GET /health` → 200 (точный путь — см.
      [observability.md](observability.md) / уточнить у команды).
- [ ] Сквозной путь MVP: вебхук `POST /webhooks/telegram/{bot_id}` принимается и
      порождает `IncomingEvent`; сценарий на `/start` отдаёт ответ (`SendMessageUseCase`).
- [ ] Проверки проходят локально: `poetry run pytest -m unit`
      (уровни — [../architecture/testing-strategy.md](../architecture/testing-strategy.md)).
- [ ] В логах при старте нет ERROR (куда смотреть — [observability.md](observability.md)).

## Типовые проблемы запуска

Дополняй таблицу при каждой новой проблеме, отнявшей > 15 минут.

| Симптом | Причина | Решение |
|---|---|---|
| `connection refused` к БД/Redis при старте | Контейнер ещё не готов, приложение стартовало раньше | Дождаться healthy: `docker compose ps`; перезапустить uvicorn |
| `ModuleNotFoundError: domain/application/...` | `src/` не в `PYTHONPATH` | `export PYTHONPATH=src` или запуск через менеджер (`poetry run`) |
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
