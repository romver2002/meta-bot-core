---
status: active
version: "1.2"
updated: 2026-07-10
verified_commit: ""
owner: ""
---

# Конфигурация meta-bot-core

Реестр всей конфигурации приложения: каждая переменная окружения, флаг и
настройка — одной строкой в таблице ниже. Стек, к которому относятся переменные
(Python 3.12 async · FastAPI · PostgreSQL 16 + SQLAlchemy 2 · Redis 7 ·
изолированный executor песочницы · TypeScript mini app) —
[../architecture/tech-stack.md](../architecture/tech-stack.md).

**Правило (жёсткое):** новая env-переменная в коде = новая строка в этом файле
**в том же PR**. Ревьюер не пропускает PR, где переменная появилась, а строки нет.

**Секреты:** в этом файле живут только **имена** переменных и место хранения.
Значения секретов не попадают ни сюда, ни в код, ни в логи — правила обращения
с секретами см. [../architecture/security.md](../architecture/security.md).
Токены платформенных ботов (`Token`) и init-данные mini app в реестре ниже
**не появляются**: они живут только в token vault за портом `TokenVaultPort`,
не в переменных окружения в открытом виде.

## Где что задаётся

- **local** — файл `.env` в корне репозитория (создаётся из `.env.example`,
  сам `.env` в `.gitignore`); порядок подъёма окружения —
  [local-dev.md](local-dev.md).
- **dev/stage/prod** — переменные CI/CD + секрет-хранилище (GitHub Environments /
  Vault / секреты CI); конкретный механизм — уточнить у команды.
- Различия значений по окружениям — см. [environments.md](environments.md).

## Реестр переменных

Секреты в столбце «Пример» не приводятся: `***`/`<...>` — плейсхолдер, реальное
значение берётся из секрет-хранилища.

| Переменная | Назначение | Где задаётся | Секрет? | Пример |
|---|---|---|---|---|
| `DATABASE_URL` | строка подключения к PostgreSQL 16 — хранилище `Bot`/`Flow`/`Session` (async SQLAlchemy) | local: `.env`; stage/prod: секрет-хранилище | **да** | `postgresql+asyncpg://meta_bot:***@localhost:5432/meta_bot` |
| `REDIS_URL` | подключение к Redis 7 — runtime-состояние FSM (`Session`) и идемпотентность вебхуков | local: `.env`; stage/prod: секрет-хранилище | **да** (в prod содержит пароль) | `redis://localhost:6379/0` |
| `SESSION_IDLE_TTL` | секунды без событий, после которых активная сессия просрочивается фоновой чисткой со стиранием переменных (BR-008) | local: `.env`; иначе: переменные CI/CD | нет | `3600` |
| `SESSION_RETENTION_DAYS` | срок хранения завершённых/просроченных сессий; старше срока — строка удаляется целиком вместе с ПДн (BR-008, [ADR-0011](../decisions/0011-session-pii-retention.md)) | local: `.env`; иначе: переменные CI/CD | нет | `30` |
| `SESSION_PURGE_INTERVAL` | интервал фоновой чистки сессий в секундах (composition root, lifespan) | local: `.env`; иначе: переменные CI/CD | нет | `3600` |
| `ADMIN_API_SECRET` | секрет для подписи/проверки токенов доступа к admin API конструктора (`presentation/api/admin_routes.py`); механизм аутентификации (JWT/сессии) — уточнить у команды | local: `.env`; stage/prod: секрет-хранилище | **да** | `<случайная строка ≥ 32 байт>` |
| `TOKEN_VAULT_URL` | адрес хранилища токенов ботов (token vault) за `TokenVaultPort`; имя условно, зависит от выбранного хранилища — уточнить у команды | local: `.env`; stage/prod: переменные CI/CD | нет | `https://vault.example.internal:8200` |
| `TOKEN_VAULT_TOKEN` | учётные данные доступа приложения к token vault; имя условно — уточнить у команды | local: `.env`; stage/prod: секрет-хранилище | **да** | `<токен доступа к vault>` |
| `MAX_API_BASE_URL` | базовый URL MAX platform-api; токен MAX передаётся адаптером в заголовке `Authorization`, **не** в query | local: `.env`; иначе: переменные CI/CD | нет | `https://platform-api2.max.ru` |
| `TELEGRAM_API_BASE_URL` | базовый URL Telegram Bot API | local: `.env`; иначе: переменные CI/CD | нет | `https://api.telegram.org` |
| `WEBHOOK_BASE_URL` | публичный HTTPS-адрес, на который платформы шлют вебхуки (`/webhooks/telegram/{bot_id}`, `/webhooks/max/{bot_id}`); для Telegram допустимы только порты 443/80/88/8443 | dev/stage/prod: переменные CI/CD | нет | `https://bots.example.com` |
| `APP_ENV` | текущее окружение (`local`/`dev`/`stage`/`prod`) — влияет на дефолты и деградации | local: `.env`; иначе: переменные CI/CD | нет | `local` |
| `LOG_LEVEL` | уровень логирования (`DEBUG`/`INFO`/`WARNING`) | local: `.env`; иначе: переменные CI/CD | нет | `INFO` |

## Фиче-флаги и прочая конфигурация

- Отдельной системы фиче-флагов пока нет — уточнить у команды по мере роста MVP
  ([../product/roadmap.md](../product/roadmap.md)).
- **Платформенные базовые URL — конфигурируемы (см. реестр). ВАЖНО (MAX):**
  проект greenfield — работаем **сразу на `platform-api2.max.ru`** (значение по
  умолчанию `MAX_API_BASE_URL`); старый `platform-api.max.ru` **не используем**,
  «миграции» у нас нет (решение 2026-07-07,
  [current/active-context.md](../current/active-context.md)). На хостах, откуда
  идут запросы, в доверенные добавляется **сертификат Минцифры**. Внешний дедлайн
  платформы 2026-07-19 (когда старый хост отключат) нас не затрагивает — мы уже на v2.
  Базовый URL — ответственность `MaxBotAdapter` (`infrastructure/platforms/max/`),
  а не бизнес-логики; приём обновлений — через webhook (ADR
  [0004-webhook-platform-integration](../decisions/0004-webhook-platform-integration.md)).
- **Webhook-хост (`WEBHOOK_BASE_URL`) по платформам:** Telegram допускает порты
  443/80/88/8443; MAX — **только 443**, с сертификатом доверенного УЦ (self-signed
  не поддерживается). Полный проверенный справочник различий (порты, авторизация,
  ретраи доставки, mini app) — [../architecture/platform-reference.md](../architecture/platform-reference.md).
- Матрица возможностей платформ (`CapabilityMatrix`) — это код/данные, а не
  env-конфиг; здесь не задаётся.

## Чек-лист: добавляю переменную

- [ ] Имя по соглашению: `UPPER_SNAKE_CASE` с префиксом подсистемы
  (`MAX_*`, `TELEGRAM_*`, `ADMIN_*`, `TOKEN_VAULT_*`, `DATABASE_*`).
- [ ] Есть безопасный дефолт в коде или явная ошибка при отсутствии — что выбрано и почему.
- [ ] Добавлена в `.env.example` (для секретов — с пустым/фиктивным значением).
- [ ] Добавлена строка в реестр выше (в том же PR).
- [ ] Секрет — заведён в секрет-хранилище для всех окружений до мерджа; токены
  ботов и init-данные mini app в env не кладём — только в token vault.
- [ ] Значение не логируется (проверь вывод конфигурации при старте) — правила
  маскирования секретов см. [../architecture/security.md](../architecture/security.md).

## Вопросы заполняющему

- Все ли переменные из кода уже в таблице? Сверь grep-ом по коду
  (например `grep -rn "os.environ" src/` / `grep -rn "getenv" src/` или по имени
  конфиг-класса настроек — конкретный класс уточнить у команды).
- Что произойдёт, если переменная не задана? Ответ должен быть предсказуемым
  (безопасный дефолт или явная ошибка при старте, без тихого запуска в проде).
