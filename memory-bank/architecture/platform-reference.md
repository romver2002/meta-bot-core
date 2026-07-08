---
status: active
version: "1.2"
updated: 2026-07-08
verified_commit: ""
owner: ""
---

# Справочник платформ: Telegram Bot API и MAX Bot API

Проверенные факты об интеграции с платформами — основа для адаптеров
(`infrastructure/platforms/*`), capability matrix и конфигурации. Ядро этих фактов
не знает (ADR [0002](../decisions/0002-domain-core-and-adapters.md)); они живут в
адаптерах и в [../ops/configuration.md](../ops/configuration.md).

> **Проверено по документации 2026-07-06.** Внешние API меняются — при расхождении
> с реальностью правьте этот документ (протокол — [../_meta/lifecycle.md](../_meta/lifecycle.md))
> и сверяйтесь с первоисточниками (ссылки внизу). Даты и лимиты — по состоянию
> на дату проверки.

## Общее

- Обе платформы дают Bot API поверх HTTPS. Приложение работает с ботом по **токену**
  уже зарегистрированного платформенного бота — конструктор аккаунт не создаёт
  (BR-001, BR-002).
- В production обновления принимаются **через webhook**, не long polling (ADR
  [0004](../decisions/0004-webhook-platform-integration.md)).
- Mini app — общий web-продукт с разными platform bridge (ADR
  [0006](../decisions/0006-mini-app-as-web-product.md)); init data валидируется
  на backend (BR-007).

## Telegram Bot API

### Приём обновлений
- Bot API — HTTP-интерфейс; бота-аккаунт создаёт **@BotFather**, он же выдаёт токен.
- Webhook: Telegram шлёт **HTTPS POST** с JSON `Update` на указанный URL. Пока
  webhook установлен, `getUpdates` (long polling) **не используется** — способы
  взаимоисключающие.
- Порты webhook: **443, 80, 88, 8443** (других нет). HTTPS обязателен (TLS 1.2+),
  self-signed сертификат допускается.
- Подсети доставки апдейтов: `149.154.160.0/20` и `91.108.4.0/22`.
- Проверка источника: секрет из `setWebhook` возвращается в заголовке
  `X-Telegram-Bot-Api-Secret-Token`.

### Mini Apps (Web Apps)
- Способы запуска: keyboard-кнопка (`web_app`), inline-кнопка, menu-кнопка, «главное»
  mini app с профиля (`https://t.me/bot?startapp`), inline-режим, прямая ссылка
  `https://t.me/bot/app`, attachment menu.
- JS API: глобальный `window.Telegram.WebApp` (скрипт `telegram-web-app.js`).
  Методы/объекты: `ready()`, `close()`, `sendData()`, `expand()`, `openLink()`,
  `MainButton`, `BackButton`, `themeParams`; события `themeChanged`, `viewportChanged`,
  `mainButtonClicked`, `backButtonClicked`.
- Данные запуска: `initData` (сырое, для валидации), `initDataUnsafe` (не доверять),
  `start_param`, `query_id`, поля пользователя/чата.
- Валидация init data на backend: `secret_key = HMAC_SHA256(bot_token, "WebAppData")`,
  затем сверить `HMAC_SHA256(data_check_string, secret_key)` с `hash`; проверить
  `auth_date` от устаревания. Сторонняя проверка без токена — по подписи Ed25519
  (`signature`) + `bot_id`.

## MAX Bot API

### Регистрация бота (на стороне MAX, вне нашего продукта)
- Бот создаётся на платформе MAX для партнёров; нужен **верифицированный профиль**:
  организация, ИП или самозанятый. С 2026 публиковать ботов и mini app можно
  только через верифицированные юрлица РФ.
- Лимиты: **5 ботов** для организации/ИП, **2 бота** для самозанятого.
- Бот проходит **модерацию**; только после неё доступен пользователям.
- После верификации в «Расширенных настройках» появляется **токен** — его наличие
  означает, что бот зарегистрирован на платформе MAX; токен — уникальный
  идентификатор для работы с API MAX (секрет, не публиковать).
- No-code конструкторы (партнёрские) подключаются так: пользователь вставляет токен
  в настройках конструктора и активирует интеграцию. Это и есть модель meta-bot-core.

### Хост, авторизация, миграция (критично)
- **Хост API: `platform-api2.max.ru`.** meta-bot-core — greenfield и использует v2
  с самого начала; старый `platform-api.max.ru` не поддерживаем, «миграции» нет
  (решение 2026-07-07, [../current/active-context.md](../current/active-context.md)).
  На хостах, откуда идут запросы, в доверенные добавляется сертификат Минцифры.
  Для справки: платформа отключает старый хост 19 июля 2026 — на нас это не влияет.
- Токен передаётся в заголовке **`Authorization: <token>`**; передача через
  query-параметр **больше не поддерживается**.

### Приём обновлений (webhook)
- Подписка: `POST /subscriptions` с телом `{ url (HTTPS-endpoint), update_types,
  secret }`. Если задан `secret`, он приходит в заголовке `X-Max-Bot-Api-Secret`
  каждого вебхука — этим проверяем источник.
- Требования: HTTPS + сертификат доверенного УЦ (self-signed не поддерживается),
  **только порт 443**.
- Доставка: при неудаче до **10 попыток** с экспоненциально растущими интервалами
  (60 c, 150 c, 375 c, …); если сервер не отвечает `200 OK` в течение **8 часов** —
  MAX автоматически отписывает бота от webhook (важно для идемпотентности и алертов,
  см. [../ops/observability.md](../ops/observability.md)).
- Long polling — ограничен по скорости и сроку хранения событий, **только для
  разработки/тестирования**, не для production.

### Mini apps
- Работают **только внутри MAX** и привязываются к конкретному чат-боту (без бота
  mini app в MAX не существует, BR-003). Собираются на обычных web-технологиях,
  выкладываются на статический **HTTPS**-хостинг; URL привязывается к боту в
  партнёрской панели (Расширенные настройки → Настроить → поле ссылки).
- MAX Bridge: скрипт `max-web-app.js` (CDN `https://st.max.ru/js/max-web-app.js`),
  глобальный объект **`window.WebApp`**. Поля/методы: `platform`
  (`ios|android|desktop|web`), `version`, `initData`/`initDataUnsafe`
  (пользователь, чат, `queryId`, `authDate`); `shareContent()`/`shareMaxContent()`,
  `BackButton`, `openLink()`/`openMaxLink()`, `openCodeReader()` (QR),
  `DeviceStorage`/`SecureStorage`, `BiometricManager`, `HapticFeedback`, NFC (Android).
- Валидация init data на backend: **тот же HMAC-алгоритм, что у Telegram** —
  `secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`, затем
  `hash == hex(HMAC_SHA256(key=secret_key, msg=data_check_string))`, сверка +
  проверка `auth_date` (BR-007). Отличие MAX — двухуровневый транспорт (фрагмент
  URL `#` → параметр `WebAppData`; `WebAppPlatform`/`WebAppVersion` в подпись НЕ
  входят) и **отдельная** формула для `requestContact` (ключ = токен напрямую,
  `phone` без `+`). Ed25519-пути (как у Telegram) у MAX нет. Пошагово оба
  алгоритма — [specs/002-platform-deep-dive](../../specs/002-platform-deep-dive/report.md) §3.

## Сводная матрица возможностей (данные для `CapabilityMatrix`)

Основа для `CapabilityMatrix` (ADR [0005](../decisions/0005-capability-matrix.md)):
единый блок конструктора доступен, только если возможность есть на платформе бота
(BR-006). Таблица — проверенный срез; полный детальный разбор с числами, лимитами
и пошаговыми алгоритмами — [specs/002-platform-deep-dive](../../specs/002-platform-deep-dive/report.md)
(верификация по офиц. докам 2026-07-08). При изменении API правится здесь.

| Возможность | Telegram | MAX | Блок / примечание |
|---|---|---|---|
| Текстовое сообщение | да | да | `Send Message` (общий) |
| Inline/callback-кнопки | да | да | `Show Buttons` (общий), разные мапперы |
| Запуск mini app | да (7 способов) | да (только внутри MAX, привязан к боту) | `Open Mini App` (общий), разный launch/bridge |
| Mini app без бота | привязан к боту | нет (только в чат-боте) | BR-003 |
| Валидация init data (HMAC) | `secret_key=HMAC("WebAppData",token)` → `HMAC(secret_key, data_check_string)` | **тот же алгоритм** (+ двухуровневый транспорт, отдельная формула requestContact) | BR-007; ядро одинаково |
| Валидация init data (Ed25519, без токена) | есть (`signature`+`bot_id`) | нет | TG-only |
| Дедуп обновлений | сквозной `update_id` | **нет per-update id** → `message.body.mid` / `callback.callback_id` / составной; `seq` не использовать | различие моделей |
| Возврат данных из mini app боту | `sendData` ≤4096B (только reply-кнопка) / `answerWebAppQuery` | **нет `sendData`** — через свой backend с валидир. initData | разные модели |
| Длина текста / callback_data | текст ≤4096 (UTF-16); `callback_data` **1–64 байта** | текст ≤4000; `payload` ≤1024 | состояние — в Redis, в кнопку короткий токен |
| Порты webhook | 443/80/88/8443 | только 443 | конфиг `WEBHOOK_BASE_URL` |
| Self-signed сертификат | допускается | не поддерживается (нужен доверенный УЦ) | |
| Авторизация API | токен в пути URL | заголовок `Authorization` | различие адаптера |
| Long polling | есть, взаимоисключимо с webhook | есть, но не для prod | ADR-0004 |
| Секрет вебхука | `X-Telegram-Bot-Api-Secret-Token` | `X-Max-Bot-Api-Secret` | |
| Ретраи доставки вебхука | любой 2XX = успех; политика не опубликована; хранение ~24 ч | до 10 (60/150/375 c…); 8 ч без `200 OK` → авто-отписка | алерт в observability |
| `Retry-After` при 429 | `parameters.retry_after` (секунды) | **не отдаёт** (требует проверки) → backoff сами | TG-only |
| Лимит частоты | по отправке: ~1/с в чат, 20/мин в группу, ~30/с рассылка | **30 rps на весь хост** `platform-api2.max.ru` | разные RateLimiter |
| QR-сканер в mini app | — | `openCodeReader()` | platform-specific |
| Биометрия / NFC / haptics в mini app | ограниченно | `BiometricManager` / NFC / `HapticFeedback` | bridge MAX богаче |
| Платежи | Telegram Payments (+ Stars/XTR): sendInvoice→pre_checkout(≤10c)→successful_payment→refund | **нет** (ни методов, ни bridge) — только внешний эквайринг через кнопку-ссылку | platform-specific, **TG-only** (ADR-0005) |

Пустая ячейка / «—» = возможности нет или она принципиально иная → в конструкторе
блок для этой платформы не предлагается, при публикации отклоняется (BR-006).

## Следствия для архитектуры

- Различия портов (Telegram 443/80/88/8443 vs MAX только 443), способов авторизации
  (Telegram — токен в URL пути, MAX — заголовок `Authorization`), bridge
  (`Telegram.WebApp` vs `window.WebApp`) и валидации init data — **всё в адаптерах**,
  а не в ядре (BR-005). Общие возможности и различия сведены в capability matrix
  ([patterns.md](patterns.md), ADR [0005](../decisions/0005-capability-matrix.md)).

## Источники (проверено 2026-07-06)

- Telegram: <https://core.telegram.org/bots/webhooks>, <https://core.telegram.org/bots/webapps>
- MAX: <https://dev.max.ru/docs/chatbots/bots-nocode/create>,
  <https://dev.max.ru/docs-api/methods/POST/subscriptions>,
  <https://dev.max.ru/docs/webapps/introduction>, <https://dev.max.ru/docs/webapps/bridge>
