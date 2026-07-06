---
status: active
version: "1.0"
updated: 2026-07-06
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
- **Миграция домена до 19 июля 2026**: перенаправить запросы с `platform-api.max.ru`
  на `platform-api2.max.ru` и добавить сертификат Минцифры в доверенные. См.
  задачу в [../current/active-context.md](../current/active-context.md).
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
- Валидация init data на backend: `HMAC_SHA256` по отсортированным параметрам с
  ключом-токеном бота, сверка с `hash` (BR-007).

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
