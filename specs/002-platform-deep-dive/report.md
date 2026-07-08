# Telegram vs MAX Bot API: тонкости, правила, функционал, ограничения

Разбор для команды meta-bot-core. Основан на верификации 8 измерений интеграции (webhooks, messaging, keyboards, mini app launch/bridge, init data, rate limits, payments, registration). Пометки уверенности: обычный текст = **подтверждено верификацией (факт)**; явное «**требует проверки**» = спорное/неподтверждённое, перед релизом сверять по первоисточнику.

Все числа и имена методов даны намеренно точно — они идут в capability matrix, конфиги адаптеров и валидаторы.

---

## 1. TL;DR — 7 самых опасных различий

1. **Идемпотентность webhook у MAX нельзя строить на «id апдейта» — его нет.** У Telegram есть сквозной монотонный `update_id` (годится и для webhook, и для polling). У MAX per-delivery id отсутствует, а MAX повторяет доставку **до 10 раз** (backoff 60/150/375 с…). Ключ дедупликации адаптер MAX синтезирует сам: для сообщений — `message.body.mid`, для колбэков — `callback.callback_id`, для остальных типов — составной ключ (`update_type + timestamp + chat_id/user_id`). **Не использовать `seq`** (он уникален лишь в пределах чата). Промах = двойное исполнение шага сценария (двойная отправка, двойное списание).

2. **Порядок аргументов HMAC при валидации init data — «грабли №1» на обеих платформах.** `secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`. Telegram в доке пишет нотацию `(msg, key)`, MAX — `(key, msg)`, но фактический вызов одинаковый: **ключ = строка `"WebAppData"`, сообщение = токен**. Перепутал местами (key=token) → другой дайджест → валидация всегда `false` для всех реальных запросов.

3. **`callback_data` Telegram — 1–64 БАЙТА, не символа.** Кириллица в UTF-8 = 2 байта/символ, эмодзи 3–4. 64 ASCII-символа влезают, ~32 кириллических — уже нет. Класть состояние сценария в `callback_data` нельзя: только короткий opaque-токен, состояние — в Redis. Превышение → `400 BUTTON_DATA_INVALID`, клавиатура не отправится. У MAX `payload` до 1024 символов — но общую схему «токен + Redis» держим и для MAX ради переносимости.

4. **Возврат данных из mini app устроен принципиально по-разному.** Telegram: нативный `WebApp.sendData(data)` (≤4096 байт) → сервисное сообщение `message.web_app_data` — но **только** из кнопки reply-клавиатуры (`KeyboardButton.web_app`). У MAX аналога `sendData`/`web_app_data` **нет вообще**: mini app возвращает данные через собственный backend по HTTPS с валидированным `initData`. Нельзя проектировать `MiniAppDataInboundPort` в расчёте на «данные придут апдейтом боту» — для MAX это ложно.

5. **Ретраи и 429 — противоположные модели.** Telegram при `429` отдаёт машиночитаемый `parameters.retry_after` (Integer, **секунды**) — ждать ровно столько. MAX **не отдаёт** `Retry-After` (по докам; эмпирически не подтверждено — **требует проверки**) → backoff (экспонента + jitter) пишем сами. Лимиты тоже разной природы: Telegram лимитирует **отправку** (≈1 msg/с в чат, 20 msg/мин в группу, ≈30 msg/с рассылка), MAX — **запросы к хосту** (30 rps суммарно на `platform-api2.max.ru`, включая `GET /updates` и `POST /subscriptions`).

6. **Платежи — чистый platform-specific: у MAX их нет ни в Bot API, ни в bridge.** Telegram: полный стек `sendInvoice → pre_checkout_query → successful_payment → refund` + Telegram Stars (XTR), с жёстким окном **10 секунд** на `answerPreCheckoutQuery`. У MAX — 0 методов, 0 событий, нет кнопки `pay`. Блок «Оплата» реализуется только в Telegram-адаптере; для сценария с MAX-платформой публикация блока оплаты отклоняется на этапе валидации.

7. **Готовность бота: Telegram — мгновенно, MAX — через обязательную модерацию.** Telegram-бот работоспособен сразу после `/newbot` у @BotFather. MAX-бот создаётся веб-формой на `business.max.ru`, проходит модерацию **до 48 часов по рабочим дням** и **не выдаёт токен и не находится в поиске** до статуса «создан». Доменная модель готовности бота обязана различать `на модерации`/`создан`/`требует исправлений`. Плюс: у MAX жёсткий лимит **5 ботов** (юрлицо/ИП) / **2 бота** (самозанятый) на верифицированный профиль-резидент РФ; у Telegram документированного лимита нет.

---

## 2. Восемь измерений: Telegram | MAX | что делаем в адаптере

### 2.1 Webhooks / приём обновлений

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Установка webhook | Метод `setWebhook` (взаимоисключающ с `getUpdates`) | REST-ресурс `POST /subscriptions` (+ `GET`/`DELETE /subscriptions`) | `register_webhook(url, allowed_types, secret)` → `setWebhook` / `POST /subscriptions`; `unregister` → `deleteWebhook` / `DELETE /subscriptions` |
| Проверка источника | Заголовок `X-Telegram-Bot-Api-Secret-Token`; `secret_token` 1–256, `[A-Za-z0-9_-]` | Заголовок `X-Max-Bot-Api-Secret`; `secret` **5–256**, `[A-Za-z0-9-]` | Разные имена заголовков и паттерны; секрет — в защищённом хранилище (token_vault), не логировать |
| Per-update id | `update_id` (Integer, монотонный) — для webhook и polling | **нет** per-delivery id; `marker` есть только в `GET /updates` | Дедуп: TG — по `update_id`; MAX — `message.body.mid` / `callback_id` / составной ключ. Отдельный `IdempotencyKeyExtractor` |
| Ретраи доставки | Есть; успех = **любой 2XX**; Telegram «сдаётся после разумного числа попыток» (точная политика **не опубликована**); недоставленные хранятся **не дольше ~24 ч** | **до 10 попыток**, backoff ×2.5: 60 с, 150 с, 375 с…; ответ **HTTP 200 за 30 с**; без успеха **8 часов → авто-отписка** | MAX: health-monitor + авто-переподписка + алерт. Оба: отвечать 200 быстро, обработку — асинхронно (очередь) |
| Порты / сеть | **443, 80, 88, 8443**; HTTPS; self-signed допускается; IP-allowlist `149.154.160.0/20`, `91.108.4.0/22` | **только 443**; HTTPS; с 25.05.2026 self-signed запрещён (нужен доверенный УЦ/Минцифры); **IP-allowlist не опубликован** | Флаги матрицы: `port_restricted`, `publishes_ip_allowlist` — только TG. Для MAX безопасность на секрете, не на IP |
| Фильтр типов | `allowed_updates` (по умолчанию исключает `chat_member`, `message_reaction`, `message_reaction_count`); не хранится между вызовами | `update_types` (список из 15 значений); дефолт при пустом — **не документирован (требует проверки)** | Всегда передавать явный список типов при subscribe, не полагаться на дефолт |
| Long polling | `getUpdates` (`offset`, `limit` 1–100, `timeout`) | `GET /updates` (`limit` 1–1000/деф.100, `timeout` 0–90/деф.30, `marker`); помечен «не для prod» | Общий `PollingReceiver` только для локальной разработки |
| Ответ на подписку | — | `SimpleQueryResult {success: bool, message?: string}`; **id подписки не отдаётся** — ключ = `url`; `GET /subscriptions` возвращает **список** (несколько подписок на бота) | Подписку идентифицировать по `url`; парсить `success`, а не `id`; модель хранения — «несколько подписок на бота» |

Полный список update-типов MAX (15, канон — `objects/Update`): `message_created`, `message_edited`, `message_removed`, `message_callback`, `bot_added`, `bot_removed`, `bot_started`, `bot_stopped`, `user_added`, `user_removed`, `chat_title_changed`, `dialog_cleared`, `dialog_muted`, `dialog_unmuted`, `dialog_removed`. Enum в адаптере держать **расширяемым** (unknown-тип не должен ронять приём): Go-SDK MAX отстаёт от доки (13 констант, без `dialog_muted`/`dialog_unmuted`).

### 2.2 Messaging / форматирование

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Отправка | `POST /bot<token>/sendMessage`; `chat_id` (Integer\|@username) + `text` — в теле метода | `POST /messages`; адресат `user_id` **или** `chat_id` (integer int64) — в **QUERY**; тело `NewMessageBody` только контент | `send_message(recipient, text, format, attachments, reply_markup)`; TG кладёт адресат в тело, MAX — в query |
| Редактирование | `editMessageText`: `(chat_id + message_id)` **или** `inline_message_id` | `PUT /messages?message_id=<string>` — `chat_id` **не нужен** | Порт edit пробрасывает `chat_id` опционально (нужен только TG) |
| Удаление | `deleteMessage(chat_id, message_id)` → True; пакет `deleteMessages` | `DELETE /messages?message_id=<string>` → `{success, message?}`; нужно право бота | — |
| Тип `message_id` | **Integer** | **string** | Нейтральный тип — `str`; к int приводить только внутри TG-адаптера |
| Лимит текста | **1–4096** символов, **UTF-16 code units**, «after entities parsing» | **до 4000** символов; единица счёта (UTF-16 vs code points) **не указана — требует проверки** | Сплиттер меряет TG в UTF-16 (`len(s.encode('utf-16-le'))//2`); кросс-платформенный порог — **4000** |
| Подпись медиа | `caption` **0–1024** | — | Отдельный лимит, не путать с 4096 |
| Форматирование | `parse_mode` = `HTML` / `MarkdownV2` / `Markdown`(legacy); либо `entities` | `format` = `markdown` / `html` (по умолчанию без разметки) | Единый внутренний markup + per-platform рендерер (см. ниже) |
| Медиа | Прямая multipart-загрузка / URL / `file_id` в `sendPhoto`/`sendDocument`/… | Двухфазно: `POST /uploads?type=image\|video\|audio\|file` → upload URL → залить файл (`multipart`, поле `data`) → `token` → `attachments:[{type, payload:{token}}]` | Порт вложений допускает двухфазный флоу; MAX инкапсулирует загрузку. Для image допустим `payload.url` вместо token — **требует проверки** |
| Форма ответа | `editMessageText` → `Message` (или `True` для inline); `deleteMessage` → `True` | `POST /messages` → `{"message": Message}` (**Message завёрнут в ключ `message`**); `PUT`/`DELETE` → `{success, message?}`, где `message` — **строка ошибки**, не объект | Разбор ответа разный: у MAX `message` значит разное в POST vs PUT/DELETE — нельзя парсить единообразно |
| Вложения при edit (MAX) | — | `attachments=null` = не менять; `[]` = удалить все | Модель вложений явно различает «не трогать» и «очистить» |

Лимиты медиа MAX: image ≤ 50 MB и ≤ 7680×7680 px; video ≤ 250 MB; audio ≤ 256 MB и ≤ 60 мин; file ≤ 4 GB. Вложений на сообщение — **не более 12**. `sendMediaGroup` Telegram — **2–10** элементов (photo+video вместе; audio только с audio, document только с document).

Правила экранирования **MarkdownV2 (Telegram)** — ядро TG-рендерера, вынести в утилиту с тестами:
- В обычном тексте экранировать `\` перед **18 символами**: `_ * [ ] ( ) ~ ` `` ` `` `> # + - = | { } . !`
- Внутри `code`/`pre` — только `` ` `` и `\`.
- Внутри `(...)` inline-ссылки и custom emoji — только `)` и `\`.
- Сам `\` управляется отдельным правилом (не входит в «18»); для литерального слэша — `\\`.

Синтаксис **MAX** (`format=markdown`/`html`, подтверждён): курсив `_t_`/`*t*` (`<i>`/`<em>`); жирный `**t**`/`__t__` (`<b>`); зачёркнутый `~~t~~` (`<del>`/`<s>`); **подчёркнутый `++t++`** (`<ins>`/`<u>`) — в TG такого нет; моноширинный `` `code` `` (`<pre>`/`<code>`); **highlight `^^t^^`** (`<mark>`); заголовки `# t` / `<h1>…<h6>`; цитата `> t` / `<blockquote>`; упоминание `[Имя](max://user/<id>)` / `<a href="max://user/<id>">` (схема `max://user/`, **не** `tg://user`). **Правила экранирования спецсимволов в MAX markdown в доке не описаны — требует проверки.** Безопасно: для пользовательского текста слать `format=html` и экранировать `< > &`.

**Не закладывать** метод `sendRichMessage` / поле `rich_message` (якобы Bot API 10.1, июнь 2026) — **требует проверки первоисточника**, вероятна галлюцинация конвертера; держать за feature-flag.

### 2.3 Keyboards / кнопки

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Виды клавиатур | **ДВА**: inline (`InlineKeyboardMarkup`, на сообщении) + reply/custom (`ReplyKeyboardMarkup`, заменяет ввод, persistent) | **ОДИН**: inline как attachment `{type:"inline_keyboard", payload:{buttons:[[...]]}}` | Нейтральный DTO `Keyboard/Button` (text+kind+payload/url/webapp); «inline vs reply» — деталь адаптера. Persistent reply — TG-only в матрице |
| Данные кнопки | `callback_data` **1–64 байта** → `CallbackQuery.data` | `payload` **≤1024** символов → `Callback.payload` | Только короткий токен; состояние — в Redis (обе платформы) |
| Ответ на нажатие | `answerCallbackQuery` **обязателен** (гасит спиннер); `callback_query_id` в теле; `text` **0–200**; `show_alert` (модальный алерт); `cache_time` (сек); правка сообщения — отдельными методами | `POST /answers?callback_id=<id>` (id в **QUERY**); тело `{message?, notification?}` — за один вызов и правит сообщение, и шлёт тост | Порт `answer_callback` с разной оркестрацией: TG — `answerCallbackQuery` (+ при необходимости `editMessageText`); MAX — один `POST /answers` |
| Обязательность ответа | Явно: без вызова у пользователя вечно крутится спиннер | В доках **не зафиксировано — требует проверки**; политика: всегда звать `/answers` (defensive) | Всегда отвечать; `callback_id`/`query_id` — транзиентно, отвечать быстро, повтор — идемпотентно |
| Лимиты раскладки | В таблицах Bot API **не задокументированы** (MTProto ~100 кнопок, ~8 в ряду) | **210 кнопок / 30 рядов / ≤7 в ряду** (≤3, если в ряду есть `link`/`open_app`/`request_geo_location`/`request_contact`); `text` кнопки 1–128; `url` link ≤2048 | Compile-time валидация раскладки под целевую платформу; лимиты MAX зашить в валидатор (схема их не отвергает) |
| Уникальные типы | `login_url`, `switch_inline_query` (3 вида), `copy_text`, `pay`, `callback_game` | `message`, `clipboard`, `chat` | Помечать в матрице как platform-only; валидатор ругается при недоступности |
| Общие (маппятся) | `callback`, `url`, `web_app`, `request_contact` (только reply), `request_location` (только reply) | `callback`, `link`, `open_app`, `request_contact` (внутри inline!), `request_geo_location` (внутри inline!) | request_contact/geo у MAX — внутри inline; у TG — только в reply |

Типы кнопок MAX (по живой OpenAPI-схеме, discriminator `type`, **8 значений**): `callback`, `link`, `request_contact`, `request_geo_location`, `chat`, `message`, `open_app`, `clipboard`. Внимание: `chat` **есть в схеме**, хотя на html-странице dev.max.ru перечислены только 7 — источник истины = схема. `intent` — это **поле** `CallbackButton` (`positive`/`negative`/`default`, влияет на визуал), **а не тип**. Разные лимиты payload: `CallbackButton.payload`/`ClipboardButton.payload` = 1024, но `OpenAppButton.payload` = pattern `^[\w-]{0,512}$` (≤512, `[A-Za-z0-9_-]`) — валидировать по-разному.

### 2.4 Mini app: запуск и bridge

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Точки запуска | **7**: reply-кнопка `web_app`, inline-кнопка `web_app`, menu-кнопка (`setChatMenuButton`+`MenuButtonWebApp`), inline-режим (`answerInlineQuery` + `InlineQueryResultsButton`), именованная ссылка `t.me/bot/app`, главная ссылка `t.me/bot?startapp`, attachment-меню | По сути **1 модель**: кнопка запуска, привязанная к боту в панели + ссылка `https://max.ru/<botName>?startapp=<payload>` | Матрица: `telegram.miniapp.launch={keyboard,inline,menu,inline_mode,attachment,deeplink}`; `max.miniapp.launch={bot_button,deeplink}` |
| JS-мост | `telegram.org/js/telegram-web-app.js`, `window.Telegram.WebApp` | `https://st.max.ru/js/max-web-app.js`, **`window.WebApp`** | Тонкий `BridgeFacade` с общими примитивами + capability-флаги |
| Lifecycle / UI | `ready()`, `expand()`, `close()`; `MainButton`+`SecondaryButton`, `BackButton`, `HapticFeedback`, `CloudStorage`, `BiometricManager` | **`ready()` и `MainButton` НЕ найдены**; `BackButton` есть (`show/hide/onClick/offClick/isVisible`); богатый device-API | На MAX нижнюю главную кнопку рисуем своим UI; версию проверяем вручную по `window.WebApp.version` |
| Событийная модель | `onEvent`/`offEvent` (шина событий) | **Нет `onEvent`/`subscribe`** — только per-component колбэки (`BackButton.onClick`) + методы (часто async) | `BridgeFacade` строим на «вызов метода + per-component callback», не на общей шине |
| Возврат данных | `sendData(data)` ≤**4096 байт** → `web_app_data` (**только reply-кнопка**); `answerWebAppQuery(web_app_query_id, result)` для inline/menu/attachment | **Нет `sendData`/`web_app_data`**: возврат через свой backend (валидированный `initData`) или `shareMaxContent({text,link}\|{mid,chatType})` | `MiniAppDataInboundPort` с двумя реализациями (см. §2.7 и раздел 3) |
| Device-API MAX | Частично перекрыт (`CloudStorage`, биометрия, QR-popup) | `openCodeReader` (QR), `DeviceStorage`/`SecureStorage` (**10 ключей**), `BiometricManager`, `NfcManager` (Android), `ScreenCapture`, `requestScreenMaxBrightness`, `downloadFile`, `requestContact` | Матрица явно кодирует «нет в web» у MAX: `shareContent`, `HapticFeedback`, Storage.clear, Biometric (web/desktop) |
| Лимиты | `sendData` ≤4096 байт; URL — HTTPS | URL mini app ≤**1024** символов, `[A-Za-z0-9.-]`, только `https://`; `startapp` ≤**512** символов `[A-Za-z0-9_-]` (превышение → payload **тихо вырезается** из URL) | Лимиты — в platform-конфиги; валидировать формы конструктора жёстко (иначе молчаливая потеря payload) |

### 2.5 Mini app: валидация init data

Криптоядро **идентично** обеим платформам (см. подробный разбор в разделе 3): `secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`, затем `hash = hex(HMAC_SHA256(key=secret_key, msg=data_check_string))`.

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Транспорт init data | Плоская query-строка `Telegram.WebApp.initData` (один уровень парсинга) | Фрагмент `#` → параметр `WebAppData` → внутренние пары (**два уровня**) | Договориться с фронтом, что MAX шлёт именно значение `WebAppData` (== `window.WebApp.initData`) |
| Исключаемые из подписи поля | **только `hash`** (поле `signature` **оставить**!) | только `hash` (поля `signature` у MAX нет) | Общий helper + разный препроцессинг |
| Внешние поля вне подписи | — | `WebAppPlatform`, `WebAppVersion` — во фрагменте, **в подпись не входят** | Подписывать только внутренние пары `WebAppData` минус `hash` |
| Второй метод | **Ed25519** (`signature` base64url + `bot_id` + публичный ключ Telegram) — проверка **без токена** | **нет** (только HMAC по токену) | `miniapp.initdata.ed25519` = TG-only |
| TTL `auth_date` | Число не фиксирует (на усмотрение разработчика) | Рекомендация **1 час (3600 с)** (со страницы bridge) | Конфиг `max_age`; анти-replay всегда, помимо HMAC |
| Отдельная формула | — | `requestContact`: `HMAC_SHA256(authDate+phone+userId через '\n', ключ=botToken)`, phone **без `+`**, `version` не хешируется | Для requestContact — **отдельный** валидатор (ключ = токен напрямую, не производный) |

Публичные ключи Ed25519 Telegram: prod `e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d`, test `40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec`.

### 2.6 Rate limits / flood control

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Природа лимита | Лимит **отправки** сообщений; единого глобального rps нет | Лимит **запросов к хосту**: **30 rps** суммарно на `platform-api2.max.ru` (включая `GET /updates`, `POST /subscriptions`, `POST /messages`) | Разные RateLimiter'ы за портом |
| Числа | ~1 msg/с в чат; **20 msg/мин** в группу (жёстко); ~**30 msg/с** рассылка | 30 rps на хост (**без per-token множителя**); per-chat/per-group лимитов нет | TG — token-bucket по осям (per-chat/per-group/broadcast); MAX — один общий распределённый счётчик 30 rps на все боты |
| Обработка 429 | `parameters.retry_after` (Integer, **секунды**) — ждать ровно столько; поле Optional (не гарантировано в каждом 429) | **Нет `Retry-After`** (по докам; **требует эмпирической проверки**) | `supports_retry_after`: TG=true, MAX=false. TG — читать поле + fallback backoff; MAX — экспонента+jitter, проактивно ≤30 rps (~33 мс между запросами); соблюдать `Retry-After`, если он всё же придёт |
| Масштабирование | Платный broadcast до **1000 msg/с** (0.1★/сообщение, порог 100k Stars + 100k MAU); рассылку советуют растягивать на **8–12 ч** | Платного повышения нет | Планировщик рассылок: TG умеет растягивать/включать paid broadcast |
| Спец-случай | `migrate_to_chat_id` (группа→супергруппа) в `ResponseParameters` | нет | TG-адаптер ловит ошибку, подставляет новый `chat_id`, повторяет; событие «миграция чата» не протекает во flow |
| Тест-окружение | Флуд-лимиты строже, числа могут меняться → **не хардкодить** | — | Все пороги — в capability matrix/конфиге, не в бизнес-логике |
| HTTP-коды | `ok:false` + `description` + `error_code` + `parameters` | Явные коды: 200/400/401/404/405/429/503 (нет 500 в списке; 5xx трактовать обобщённо) | Разбор ошибок per-platform |

### 2.7 Payments

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Наличие | Полный стек | **Отсутствует** (0 методов, 0 событий, нет кнопки `pay`, нет bridge-метода оплаты) | Платежи — опциональная `PaymentsCapability`, реализует **только** TG-адаптер; MAX → `NotSupported` |
| Флоу | `sendInvoice` → (`shipping_query`→`answerShippingQuery` при `is_flexible`) → `pre_checkout_query` → `answerPreCheckoutQuery` (**≤10 с!**) → `successful_payment` → выдача | — | Доменные события `pre_checkout`/`successful_payment`; хендлер отвечает в окне 10 с, выдачу — после `successful_payment` |
| Два мира | Провайдерский (фиат, `provider_token`, shipping) + Telegram Stars (`currency="XTR"`, `provider_token` пустой, рефанды `refundStarPayment`, подписки, paid media) | — | Две под-capability внутри TG |
| Кнопка оплаты | `reply_markup` опционален (пусто → Telegram сам покажет «Pay total price»); если задан — **первая кнопка** обязана быть `InlineKeyboardButton(pay=true)`, первой в первом ряду, только в инвойсах | — | Генератор клавиатуры инвойса: либо без `reply_markup`, либо `pay=true` первой |
| Суммы | `LabeledPrice.amount` — **целое в минимальных единицах** (масштаб по `exp` из `currencies.json`, USD exp=2: $1.45→145; JPY exp=0); фиат ~US$1–10000, ≤12 цифр; XTR = число звёзд | — | Масштабировать по `exp` конкретной валюты, **не** хардкодить ×100 |
| Подписки Stars | `createInvoiceLink` + `subscription_period=2592000` (30 дней, **единственное** значение); отмена `editUserStarSubscription(user_id, telegram_payment_charge_id, is_canceled)` | — | Рекуррентные платежи — telegram-only в матрице |
| Обход для MAX | — | Только внешний эквайринг: кнопка `link` / `open_app` на свой платёжный провайдер (вне API MAX) | При платформе MAX блок оплаты дизейблить, предлагать link/open_app как неплатёжный блок |

Поля `SuccessfulPayment`: `currency`, `total_amount` (Integer, мин. единицы), `invoice_payload`, `subscription_expiration_date` (Integer Unix ts, Optional), `is_recurring` (тип `True`, приходит только когда истинно), `is_first_recurring` (тип `True`), **`shipping_option_id`** (Optional), **`order_info`** (Optional — пропущены в исходной сводке), `telegram_payment_charge_id`, `provider_payment_charge_id`. В БД: `is_recurring`/`is_first_recurring` как nullable/`DEFAULT false`; `subscription_expiration_date` как BIGINT/timestamptz. `provider_token` — секрет провайдера, хранить в token_vault.

### 2.8 Регистрация, лимиты, авторизация

| Аспект | Telegram | MAX | Что делаем в адаптере |
|---|---|---|---|
| Создание бота | Чат-команда `/newbot` у @BotFather; активация мгновенная, без модерации | **Веб-форма на `business.max.ru`** (мастер-бота/`/newbot` **нет**); Имя 1–59, Логотип 500×500 ≤5 МБ, Описание ≤200 | Онбординг: BR-001 — токен приносит пользователь; модель готовности различает состояния |
| Модерация | Нет | **Обязательна, до 48 ч по рабочим дням**; статусы `на модерации`/`создан`/`требует исправлений`; токен и поиск — только после «создан» | Домен: бот работоспособен = статус «создан» + выданный токен |
| Кто может | Любой аккаунт по телефону, без верификации | Только верифицированные **юрлицо/ИП/самозанятый — резиденты РФ** (Госуслуги / Alfa ID / Т-Business ID) | — |
| Лимит ботов | В доках не задокументирован | **5** (юрлицо/ИП) / **2** (самозанятый) на профиль | Модель мультибота/тарификации учитывает лимит MAX |
| Место токена в запросе | В **пути URL**: `https://api.telegram.org/bot<token>/METHOD` | Заголовок **`Authorization: <token>`** (raw, **без `Bearer`**); query `access_token` **не поддерживается**; хост `platform-api2.max.ru` | Транспортный адаптер параметризует способ передачи токена; для MAX — доверенный сертификат Минцифры в TLS-trust |
| Формат токена | Структурированный `<bot_id>:<hash>` (напр. `123456:ABC-DEF...`) — валидируем `^\d+:[\w-]+$` | **Не документирован** (непрозрачная строка) | Для MAX строгую регэксп-валидацию **не включать** (риск отклонить валидный токен): только «непустая строка без пробелов» |
| Идентичность | `username` выбирает пользователь (обязан кончаться на `bot`, иммутабелен) | Ник генерится системой: `id<ИНН>_bot` / `se(orgid)_bot` | — |
| Перевыпуск токена | `/token` у @BotFather | В «Расширенных настройках» панели | — |

---

## 3. Валидация init data — пошагово (самое частое место ошибок)

Криптоядро у Telegram и MAX **одинаковое**. Различается только препроцессинг (парсинг строки и набор исключаемых полей). Общий helper с явной сигнатурой `hmac_webapp_signature(token, data_check_string)`, где `key=b"WebAppData"`, `message=token` для `secret_key` — чтобы навсегда убить путаницу нотаций.

### 3.1 Telegram — метод по токену (HMAC-SHA256)

Источник: `window.Telegram.WebApp.initData` — готовая URL-encoded query-строка (один уровень). `initDataUnsafe` — **не для валидации**.

1. Распарсить query-строку в пары `key=value` (значения — уже URL-декодированные).
2. **Исключить только поле `hash`.** Поле `signature` (на клиентах Bot API 8.0+) **оставить в строке** — оно входит в набор, покрываемый серверным `hash`. (Это опровержение частой ошибки; см. раздел 6.)
3. `data_check_string` = пары `key=<value>`, отсортированные по ключу по алфавиту, соединённые `\n` (0x0A). `user`/`receiver`/`chat` — JSON-строки, входят целиком как значение.
4. `secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)`.
5. Сверить `hex(HMAC_SHA256(key=secret_key, msg=data_check_string))` (нижний регистр, constant-time) с полем `hash`.
6. Дополнительно проверить `auth_date` (Unix ts, секунды) на устаревание.

### 3.2 Telegram — сторонний метод (Ed25519, без токена)

1. `data_check_string` = `<bot_id>:WebAppData` + `\n` + все поля **кроме `hash` И `signature`**, отсортированные по алфавиту, `key=<value>`, через `\n`. Пример: `12345678:WebAppData\nauth_date=<...>\nquery_id=<...>\nuser=<...>`.
2. `signature` — base64url (без паддинга) → 64 байта.
3. `Ed25519_verify(public_key_env, data_check_string, signature)`; ключ выбирать по окружению (prod/test).

Значения полей берутся как есть (без повторного url-decode перед сборкой строки).

### 3.3 MAX — метод по токену (HMAC-SHA256)

Источник: `window.WebApp.initData`. Двухуровневый транспорт: фрагмент URL после `#` = `WebAppData=<...>&WebAppPlatform=<...>&WebAppVersion=<...>`; валидируется **только внутреннее `WebAppData`**.

1. Распарсить `WebAppData` (split по `&`, затем по первому `=`) в пары `[[key,value]...]`.
2. Убедиться, что `hash` встречается ровно один раз; сохранить и **исключить** его.
3. **URL-декодировать все значения** (`decodeURIComponent`) — **до** сортировки; **не** реэнкодить.
4. Отсортировать пары по ключу по алфавиту a→z (в референсе `localeCompare`; для реальных ключей MAX — нижний snake_case — эквивалентно ordinal-`sorted()`; см. раздел 6).
5. `launch_params` = оставшиеся пары `key=value` через `\n`. **`WebAppPlatform`/`WebAppVersion` НЕ включать** (они внешние, вне `WebAppData`).
6. `secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)`.
7. `hex(HMAC_SHA256(key=secret_key, msg=launch_params))` (нижний регистр) сверить с сохранённым `hash`.
8. Проверить `auth_date` (Unix ts, секунды) на устаревание — рекомендация MAX **1 час** (3600 с).

Поля MAX `initDataUnsafe`: `query_id` (UUID), `auth_date`, `hash`, `ip`, `user{id,first_name,last_name,username,language_code,photo_url}`, `chat{id,type:"DIALOG"|"CHAT"|"CHANNEL"}`, `start_param`. У MAX Ed25519-пути нет — только HMAC по токену.

### 3.4 MAX — отдельный флоу `requestContact` (НЕ путать с initData)

`HMAC_SHA256(authDate + phone + userId, botToken)` — **ключ = botToken напрямую** (без промежуточного `WebAppData`); поля соединяются `key=value` через `\n`; `phone` **без ведущего `+`** (`7...`, не `+7...`); `version` не участвует. **Точное написание ключей** (`auth_date` vs `authDate`, `user_id` vs `userId`) в доке противоречиво — **требует проверки** прямым чтением примера кода на `/docs/webapps/bridge`.

### 3.5 Ключевые «грабли»

- **Порядок аргументов HMAC** (раздел 1, п.2) — ключ всегда `"WebAppData"`, сообщение — токен.
- **Telegram: `signature` НЕ исключать** в HMAC-методе (исключать оба поля — только в Ed25519).
- **MAX: `WebAppPlatform`/`WebAppVersion` не подписывать**, декодировать до сортировки, не реэнкодить.
- **initData MAX = алгоритм Telegram** (двухшаговый `WebAppData`) — общий валидатор переиспользуем; отдельный нужен **только** для `requestContact`.
- Токен для HMAC — из token_vault; `initData`/`hash`/секреты не логировать. Ed25519-путь Telegram — единственный, кому токен не нужен.

Юнит-тесты на известных векторах для обеих платформ обязательны.

---

## 4. Матрица возможностей (уточнение к platform-reference.md)

Легенда: **общий** блок = есть у обеих (маппится); **platform-specific** = только на одной; **недоступно** = принципиально нет.

| Возможность | Telegram | MAX | Классификация | Блок / примечание |
|---|---|---|---|---|
| Текстовое сообщение | ✅ ≤4096 (UTF-16) | ✅ ≤4000 | **общий** | `Send Message`; кросс-порог 4000 |
| Форматирование текста | HTML/MarkdownV2 (18 escape) | markdown/html (escape **не докум.**) | **общий**, рендереры разные | escape MAX — требует проверки |
| Inline/callback-кнопки | ✅ | ✅ | **общий** | `Show Buttons`; разные мапперы и лимиты |
| Reply/persistent-клавиатура | ✅ | ❌ | **TG-only** | у MAX request_contact/geo — внутри inline |
| Кнопка copy_text / login_url / switch_inline | ✅ | ❌ | **TG-only** | |
| Кнопка message / clipboard / chat | ❌ | ✅ | **MAX-only** | `chat` есть в схеме MAX |
| Запуск mini app | ✅ 7 способов | ✅ 2 (bot_button, deeplink) | **общий**, launch/bridge разные | `Open Mini App` |
| Mini app без бота | привязан к боту | ❌ (только в чат-боте) | — | BR-003 |
| Возврат данных из mini app боту | `sendData`(≤4096B, только reply) / `answerWebAppQuery` (inline/menu/attach) | ❌ нативно — через свой backend/`shareMaxContent` | **разные модели** | `MiniAppDataInboundPort` 2 реализации |
| MainButton в mini app | ✅ | ❌ (свой UI) | **TG-only** | |
| QR-сканер / SecureStorage / NFC / Biometric в mini app | частично | ✅ богаче | **MAX богаче** | `openCodeReader`, Storage 10 ключей |
| Валидация init data (HMAC) | ✅ | ✅ **тот же алгоритм** | **общий** | ⚠ исправление к prior (было «разные») |
| Валидация init data (Ed25519, без токена) | ✅ | ❌ | **TG-only** | ключи prod/test |
| Порты webhook | 443/80/88/8443 | только 443 | различие | конфиг `WEBHOOK_BASE_URL` |
| Self-signed сертификат | допускается | ❌ (доверенный УЦ) | различие | |
| IP-allowlist серверов | ✅ 2 подсети | ❌ не опубликован | **TG-only** | безопасность MAX — на секрете |
| Авторизация API | токен в пути URL | заголовок `Authorization` (без Bearer) | различие | |
| Per-update id / дедуп | `update_id` | ❌ (mid/callback_id/составной) | **разные модели** | `IdempotencyKeyExtractor` |
| Ретраи webhook | ~24ч, 2XX, политика не докум. | 10 попыток, 8ч→авто-отписка | различие | health-monitor + re-subscribe (MAX) |
| 429 retry_after | ✅ (секунды) | ❌ (**требует проверки**) | **TG-only** | `supports_retry_after` |
| Rate limit | по отправке (1/с, 20/мин, 30/с) | 30 rps на хост | различие | разные RateLimiter |
| Платный broadcast (1000/с) | ✅ | ❌ | **TG-only** | |
| **Платежи (invoice/checkout/refund/Stars)** | ✅ полный стек | ❌ **недоступно** | **TG-only** | ⚠ исправление: у MAX **нет** «иных механик» в API |
| Long polling | ✅ (взаимоискл. с webhook) | ✅ (не для prod) | **общий** | ADR-0004 |

### Исправления к таблице в platform-reference.md (строки 116–132)

1. **Строка «Валидация init data»**: сейчас `алгоритмы разные` — **неверно**. Алгоритм HMAC для initData **идентичен** (двухшаговый ключ `WebAppData`). Разной является только отдельная формула MAX для `requestContact` (телефон) и наличие Ed25519 у Telegram. Заменить на: «HMAC-алгоритм initData одинаков; у TG дополнительно Ed25519, у MAX — отдельная формула для requestContact».
2. **Строка «Платежи»**: сейчас `Telegram Payments | иные механики` — **вводит в заблуждение** (у MAX «иных механик» нет). Заменить на: `Telegram Payments (+ Stars) | нет (только внешний эквайринг через link/open_app) | platform-specific, TG-only`.
3. Добавить строки: «Per-update id / дедуп», «429 retry_after», «MainButton в mini app», «Возврат данных из mini app», «IP-allowlist», «Платный broadcast» — их в текущей таблице нет, а различие критично для кода.

---

## 5. Сверка с platform-reference.md: подтверждено / дополнить

### Подтверждено верификацией (оставить как есть)

- Webhook и `getUpdates` взаимоисключающи (стр. 37–38). ✅
- Порты Telegram **443/80/88/8443**, HTTPS, self-signed допускается (стр. 39–40). ✅
- Подсети Telegram `149.154.160.0/20`, `91.108.4.0/22` (стр. 41). ✅
- Заголовки секрета: `X-Telegram-Bot-Api-Secret-Token` / `X-Max-Bot-Api-Secret` (стр. 43, 86). ✅
- Хост MAX `platform-api2.max.ru`; токен в `Authorization`, query не поддерживается (стр. 76–81). ✅ (уточнение: **без `Bearer`**, raw-токен).
- MAX webhook: `POST /subscriptions {url, update_types, secret}`; **только 443**; self-signed не поддерживается (стр. 84–88). ✅
- MAX ретраи: **до 10 попыток**, 60/150/375 с, **8 ч → авто-отписка** (стр. 89–92). ✅
- MAX long polling — не для prod (стр. 93–94). ✅
- MAX лимиты ботов **5/2**, обязательная модерация, токен после верификации (стр. 63–70). ✅ (уточнение: модерация **до 48 ч по рабочим дням**; статусы `на модерации`/`создан`/`требует исправлений`).
- MAX bridge: `window.WebApp`, `https://st.max.ru/js/max-web-app.js`, набор методов (стр. 101–106). ✅
- Валидация Telegram initData `HMAC_SHA256(bot_token,"WebAppData")` + Ed25519/`bot_id` (стр. 55–58). ✅

### Нужно дополнить / поправить

1. **Минцифры-сертификат — два разных требования.** Стр. 78 говорит про доверие Минцифры на **исходящих** хостах (чтобы вызывать `platform-api2.max.ru`). Отдельно нужно добавить: **наш webhook-endpoint** обязан иметь сертификат **доверенного УЦ / Минцифры** (с 25.05.2026 self-signed и HTTP запрещены), CN/SAN = домен URL, полная цепочка. Это разные концы TLS.
2. **Дедупликация MAX.** Добавить: у MAX **нет per-update id**; ключ — `message.body.mid` (сообщения), `callback.callback_id` (колбэки), составной для прочих. Не использовать `seq`. TTL хранения ключей — ≥8 ч (окно ретраев + авто-отписка).
3. **Telegram ретраи/хранение.** Добавить: успех = **любой 2XX**; точная политика ретраев **не опубликована**; недоставленные хранятся **не дольше ~24 ч**; сброс очереди — `drop_pending_updates`; метрика залипания — `getWebhookInfo.pending_update_count`.
4. **Rate limits.** Добавить измеримые числа: Telegram ≈1 msg/с чат, 20 msg/мин группа, ≈30 msg/с рассылка, `parameters.retry_after` при 429; MAX — **30 rps на хост** (без per-token множителя; `GET /updates` и подписки едят из того же бюджета), `Retry-After` не документирован (**требует проверки**).
5. **Лимиты сообщений/клавиатур.** Добавить: text TG **4096** (UTF-16) / MAX **4000**; caption **1024**; `sendMediaGroup` **2–10**; `callback_data` **64 байта**; клавиатура MAX **210/30/7** (3 для link/open_app/geo/contact); MAX вложений **≤12**.
6. **Возврат данных из mini app.** Строку про `window.Telegram.WebApp.sendData()` (стр. 51) дополнить: `sendData` работает **только из reply-кнопки** (≤4096 байт); для inline/menu/attachment — `answerWebAppQuery`; для прямых ссылок и inline-режима **ни то, ни другое** — только свой backend. У MAX `sendData` **нет** — возврат через backend.
7. **Формат токена MAX.** Добавить: **не документирован** → для MAX строгую регэксп-валидацию не применять (только «непустая строка без пробелов»); строгий `^\d+:[\w-]+$` — только для Telegram.
8. **Форма ответа POST /messages MAX.** Уточнить: `POST` возвращает `{"message": Message}` (Message завёрнут в ключ); `PUT`/`DELETE` — `{success, message?}`, где `message` — строка ошибки, не объект.
9. **Платежи.** Пометить строку как TG-only и убрать «иные механики» у MAX (см. раздел 4).
10. **Ключи Ed25519** внести в конфиг как константы окружения (prod/test) — сейчас в тексте есть только упоминание, без значений.

---

## 6. Неподтверждённое (uncertain/refuted) — перепроверить вручную по первоисточнику

### Refuted (в исходной сводке была ошибка — исправлено выше, но зафиксировать)

1. **Telegram: исключать `signature` из `data_check_string` в HMAC-методе — НЕВЕРНО.** В HMAC-методе исключается **только `hash`**; `signature` (Bot API 8.0+) остаётся в строке (его покрывает серверный `hash`). Оба поля исключаются **только** в стороннем Ed25519-методе. Проверить дословно на `core.telegram.org/bots/webapps`. *Риск: исключив `signature`, сломаете авторизацию всем легитимным пользователям на клиентах 8.0+.*
2. **Telegram: «inline/menu/attachment/ссылки → `answerWebAppQuery`» — свалено в кучу неверно.** `query_id` (и, значит, `answerWebAppQuery`) есть только у inline-кнопки, menu-кнопки, attachment-меню. У **прямых ссылок** (`t.me/bot/app`, `startapp`) и **inline-режима** `query_id` **нет** — возврат данных только через свой backend. И «ровно 4096 байт» неточно — «**до** 4096». Проверить на `core.telegram.org/bots/webapps`.

### Uncertain — требует проверки первоисточником/эмпирикой

3. **MAX: дефолт при пустом `update_types`.** Список из 15 типов подтверждён, но **поведение фильтра при пустом/незаданном** списке в доке **не описано**. Наследие TamTam предполагает «пустой = все», но не гарантировано. → Всегда передавать явный список; проверить эмпирически (подписаться без `update_types` и сверить приходящие типы).
4. **MAX: `Retry-After` при 429.** В доках не упомянут (только код 429 и лимит 30 rps). Реальный шлюз мог бы отдавать стандартный `Retry-After` — **не проверялось живым запросом**. → Снять сырой 429 с `platform-api2.max.ru`; закладывать backoff, но соблюдать `Retry-After`, если он придёт.
5. **MAX: поведение при неотвеченном callback + TTL `callback_id`.** Объект `Callback` не содержит expiry; обязательность `/answers` и наличие спиннера — **не документированы**. → Всегда звать `POST /answers` (defensive), TTL и поведение индикатора — проверить на реальном клиенте.
6. **MAX: точное написание ключей в формуле `requestContact`** (`auth_date` vs `authDate`, `user_id` vs `userId`) и полный набор полей строки — в доке противоречиво. → Снять из примера кода на `/docs/webapps/bridge`. *Неверный регистр ключа ломает совпадение хеша.*
7. **MAX: сортировка ключей init data.** Референс использует `localeCompare`; бланкетное «ordinal ≡ localeCompare для ASCII» **ложно** (расходятся на регистре и `_` vs цифра). Для реальных ключей MAX (нижний snake_case) `sorted()` совпадает. → Использовать обычный `sorted()` по ключу, но закрыть юнит-тестом на реальном примере; при появлении заглавных/цифр/пунктуации в ключах — реплицировать collation-семантику референса.
8. **MAX: канонический TTL `auth_date`.** Страница validation числа не даёт; «1 час» взято со страницы bridge в контексте валидации телефона. → Уточнить авторитетное значение для основной проверки initData.
9. **Telegram: `sendRichMessage` / `rich_message` (якобы Bot API 10.1, 2026-06).** Не подтверждено; сильные признаки галлюцинации конвертера (реальной таблицы параметров получить не удалось). → **Не хардкодить**; проверять по сырому HTML `#sendrichmessage`/`#inputrichmessage` или дословному анонсу @BotNews; держать за feature-flag.

### Confirmed, но с открытыми под-вопросами (сверить перед реализацией)

10. **MAX text — единица счёта** (UTF-16 code units vs Unicode code points) не указана. → Консервативно резать по 4000; проверить на строке с эмодзи/суррогатами.
11. **MAX `Subscription`** — точный набор полей ответа `GET /subscriptions` (ожидаются `url`, `time`, `update_types`, `version`) и числовой лимит одновременных подписок не подтверждены дословно.
12. **MAX media** — можно ли для image давать `payload.url` вместо `token`; точное место возврата token (в ответе `/uploads` vs после заливки) для разных типов.
13. **Telegram** — дословные таблицы `#responseparameters`, `#successfulpayment`, `#edituserstarsubscription`, `#sendinvoice`, `editMessageText`/`deleteMessage` подтверждены через зеркала (aiogram/PTB); официальная `core.telegram.org/bots/api` обрезается WebFetch. Значения канонические, но при желании сверить на живых якорях.
14. **MAX** — точный статус финального этапа модерации: дока говорит «создан», часть сторонних источников — «Готов к публикации». Проверить в самом MasterBot/панели.