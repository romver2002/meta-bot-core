---
status: active
version: "1.6"
updated: 2026-07-27
verified_commit: ""
owner: ""
---

# Конфигурация meta-bot-core

Реестр всей конфигурации приложения: каждая переменная окружения, флаг и
настройка — одной строкой в таблице ниже. Стек, к которому относятся переменные
(Python 3.14 async · FastAPI · PostgreSQL 16 + SQLAlchemy 2 · Redis 7 ·
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
| `DATABASE_URL` | строка подключения к PostgreSQL 16 — хранилище `Bot`/`Flow`/`Session` (async SQLAlchemy); compose пробрасывает Postgres на порт 5433 хоста | local: `.env`; stage/prod: секрет-хранилище | **да** | `postgresql+asyncpg://metabot:***@localhost:5433/metabot` |
| `REDIS_URL` | подключение к Redis 7 — идемпотентность вебхуков (hot-FSM `Session` — план ADR-0008, пока в PG) | local: `.env`; stage/prod: секрет-хранилище | **да** (в prod содержит пароль) | `redis://localhost:6379/0` |
| `WEBHOOK_SECRET` | секрет вебхуков: сверяется с заголовком `X-Telegram-Bot-Api-Secret-Token` / `X-Max-Bot-Api-Secret` (`presentation/api/webhook_routes.py`), при несовпадении — 403; дефолт `None` = проверка **отключена** — в prod обязателен | local: `.env`; stage/prod: секрет-хранилище | **да** | `<случайная строка>` |
| `CORS_ALLOWED_ORIGINS` | точный JSON-массив origin'ов web-фронтендов, которым браузер разрешает `POST` к API (mini app auth/result); без путей и завершающего `/`, `*` запрещён; пустой массив отключает CORS | local: `.env`; stage/prod: переменные CI/CD | нет | `["https://mini.example.com"]` |
| `VITE_API_BASE_URL` | origin backend для собранного `frontend/miniapp/`; пусто = same-origin `/api`, внешний origin должен быть HTTPS (кроме `localhost`/`127.0.0.1`) | frontend/miniapp/.env локально; stage/prod: env на этапе сборки статики | нет | `https://api.example.com` |
| `WEBHOOK_BASE_URL` | публичный HTTPS-адрес приёма вебхуков; при заданном значении `publish` сам регистрирует `/webhooks/{platform}/{bot_id}` у платформы ([ADR-0014](../decisions/0014-auto-webhook-registration.md)), пусто — регистрация ручная (dev без туннеля); для Telegram допустимы порты 443/80/88/8443, для MAX — только 443 | local: `.env`; stage/prod: переменные CI/CD | нет | `https://api.example.com` |
| `WEBHOOK_IDEMPOTENCY_TTL` | TTL (секунды) ключей идемпотентности вебхуков в Redis (`infrastructure/cache/redis_idempotency.py`) | local: `.env`; иначе: переменные CI/CD | нет | `86400` |
| `EVENTS_INFLIGHT_TTL` | TTL (секунды) ключа «внешнее событие в работе» ([ADR-0019](../decisions/0019-external-event-delivery-contract.md)): ключ `event_id` живёт столько до фактического исполнения сценария и только потом продлевается до `WEBHOOK_IDEMPOTENCY_TTL`. Это единственная гарантия при kill/OOM (компенсация тогда не отработает): бери ≤ приемлемой задержки повтора у вызывающего. Под длину цепочки сценария подгонять не нужно — пока исполнение живо, аренда продлевается heartbeat'ом (`lease_heartbeat_seconds` = TTL/3, задаётся в composition root); инвариант — heartbeat заметно меньше этого TTL | local: `.env`; иначе: переменные CI/CD | нет | `120` |
| `SESSION_IDLE_TTL` | секунды без событий, после которых активная сессия просрочивается фоновой чисткой со стиранием переменных (BR-008) | local: `.env`; иначе: переменные CI/CD | нет | `3600` |
| `SESSION_RETENTION_DAYS` | срок хранения завершённых/просроченных сессий; старше срока — строка удаляется целиком вместе с ПДн (BR-008, [ADR-0011](../decisions/0011-session-pii-retention.md)) | local: `.env`; иначе: переменные CI/CD | нет | `30` |
| `SESSION_PURGE_INTERVAL` | интервал фоновой чистки сессий в секундах (composition root, lifespan) | local: `.env`; иначе: переменные CI/CD | нет | `3600` |
| `TOKEN_VAULT_FILE` | путь к файловому dev-vault токенов ботов за `TokenVaultPort` (`infrastructure/security/file_token_vault.py`); **путь — не секрет, содержимое файла — секрет** (`.secrets/` в `.gitignore`); прод-хранилище — открытый вопрос | local: `.env` / дефолт в коде | нет | `.secrets/token-vault.json` |
| `CONNECTION_SECRETS_FILE` | путь к файлу секретов подключений интеграций (`FileConnectionSecrets`); путь — не секрет, содержимое — секрет | local: `.env` / дефолт в коде | нет | `.secrets/connections.json` |
| `NOTIFICATION_TARGETS_FILE` | путь к файлу привязок «роль → chat_id» для уведомлений (ADR-0010, `FileNotificationTargets`); путь — не секрет, содержимое (потенциальные ПДн) — секрет | local: `.env` / дефолт в коде | нет | `.secrets/notification-targets.json` |
| `EVENTS_TOKENS_FILE` | путь к файлу events-токенов (ADR-0017, `FileEventsTokens`) — аутентификация `POST /bots/{id}/events`; отдельный от connections.json, `{{secret:*}}` его не видит (BR-010) | local: `.env` / дефолт в коде | нет | `.secrets/events-tokens.json` |
| `MAX_CA_BUNDLE` | путь к доп. корневому CA (сертификат Минцифры), которому доверяет **только** SSL-контекст MAX-адаптера (`infrastructure/platforms/max/tls.py`); нужен для TLS к `platform-api2.max.ru`. В глобальный `certifi` НЕ добавляется — доверие сужено (не весь исходящий трафик). Файла нет → MAX-клиент на дефолтном доверии | local: дефолт в коде; образ кладёт cert в `ops/certs/` | нет | `ops/certs/russian_trusted_root_ca.pem` |
| `PROJECT_NAME` | имя сервиса — отдаётся healthcheck'ом, по нему ищется версия пакета (`GetHealthcheckUseCase`) | local: дефолт в коде | нет | `meta-bot-core` |
| `PUBLIC_URL` | публичный URL сервиса (отдаётся healthcheck'ом) | local: дефолт в коде; stage/prod: переменные CI/CD | нет | `http://localhost:8000` |
| `LOG_LEVEL` | уровень логирования (`DEBUG`/`INFO`/`WARNING`) | local: `.env`; иначе: переменные CI/CD | нет | `INFO` |
| `LOG_DIR` | каталог файлов логов `app.log`/`errors.log` (ротация 5 МБ × 5); задаётся ТОЛЬКО локально (compose монтирует `./logs`), в проде пусто — только stdout ([ADR-0013](../decisions/0013-structured-logging.md)) | local: compose | нет | `logs` |
| `BACKUP_INTERVAL` | период `pg_dump` сервиса `pg-backup` (compose, секунды); дампы в `./backups/` на хосте (каталог с ПДн сессий, в `.gitignore`), restore — [runbooks/backup-restore.md](runbooks/backup-restore.md) | local: `.env`/дефолт compose | нет | `86400` |
| `BACKUP_KEEP_DAYS` | срок хранения дампов `pg-backup`: старше — удаляются ротацией | local: `.env`/дефолт compose | нет | `7` |

### Планируемые переменные (кодом не читаются)

Эти имена зарезервированы дизайном, но `Settings` (`src/infrastructure/config.py`)
их **не читает** — задание их в `.env` ни на что не влияет. Требования сохраняем
как план до реализации.

| Переменная | Назначение (план) | Почему пока не в коде |
|---|---|---|
| `ADMIN_API_SECRET` | секрет для подписи/проверки токенов доступа к admin API конструктора (`presentation/api/admin_routes.py`) (**секрет**) | план — аутентификация admin API не реализована (открытый вопрос IAM) |
| `TOKEN_VAULT_URL` | адрес внешнего хранилища токенов ботов (token vault) за `TokenVaultPort` | план — вместо внешнего vault работает файловый dev-vault (`TOKEN_VAULT_FILE`, см. реестр) |
| `TOKEN_VAULT_TOKEN` | учётные данные доступа приложения к внешнему token vault (**секрет**) | план — см. `TOKEN_VAULT_URL` |
| `MAX_API_BASE_URL` | базовый URL MAX platform-api; токен MAX передаётся адаптером в заголовке `Authorization`, **не** в query | план — сейчас URL это хардкод-дефолт конструктора `MaxBotAdapter` (`infrastructure/platforms/max/adapter.py`) |
| `TELEGRAM_API_BASE_URL` | базовый URL Telegram Bot API | план — сейчас URL это хардкод-дефолт конструктора `TelegramBotAdapter` (`infrastructure/platforms/telegram/adapter.py`) |
| `APP_ENV` | текущее окружение (`local`/`dev`/`stage`/`prod`) — влияет на дефолты и деградации | план — разделения окружений в `Settings` нет |

## Фиче-флаги и прочая конфигурация

- Отдельной системы фиче-флагов пока нет — уточнить у команды по мере роста MVP
  ([../product/roadmap.md](../product/roadmap.md)).
- **Платформенные базовые URL** сейчас — параметры конструкторов адаптеров с
  хардкод-дефолтами (`infrastructure/platforms/telegram/adapter.py`,
  `infrastructure/platforms/max/adapter.py`); env-переменных для них нет,
  конфигурируемость через env — план (см. «Планируемые переменные»).
  **ВАЖНО (MAX):** проект greenfield — работаем **сразу на `platform-api2.max.ru`**
  (дефолт конструктора `MaxBotAdapter`); старый `platform-api.max.ru`
  **не используем**, «миграции» у нас нет (решение 2026-07-07,
  [current/active-context.md](../current/active-context.md)). **Сертификат
  Минцифры** vendored в `ops/certs/russian_trusted_root_ca.pem` и добавляется
  в certifi при сборке образа (`Dockerfile`) — ручной настройки хостов не
  требуется ([../architecture/deployment.md](../architecture/deployment.md)).
  Внешний дедлайн платформы 2026-07-19 (когда старый хост отключат) нас не
  затрагивает — мы уже на v2. Базовый URL — ответственность `MaxBotAdapter`
  (`infrastructure/platforms/max/`), а не бизнес-логики; приём обновлений —
  через webhook (ADR
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
  (например `grep -rn "os.environ" src/` / `grep -rn "getenv" src/`) и с полями
  конфиг-класса `Settings` (`src/infrastructure/config.py`, pydantic-settings).
- Что произойдёт, если переменная не задана? Ответ должен быть предсказуемым
  (безопасный дефолт или явная ошибка при старте, без тихого запуска в проде).
