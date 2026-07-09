# Первый бот — «Умный помощник по заявкам»

Первый живой бот платформы, собранный **как ДАННЫЕ**: один `Flow`
([flow.definition.json](flow.definition.json)) из общих блоков. В ядро/движок
не попадает ничего бото-специфичного — OpenRouter, системный промт, база знаний,
меню, тексты и форма живут в `params` узлов, а не в коде (принцип «конструктор,
а не заточенность под одного»).

## Что внутри Flow

28 узлов: каркас (приветствие, меню-хаб, «Что умею», «Услуги», «Частые вопросы»),
живой AI-ответ через OpenRouter, форма заявки с доставкой админу (блок `notify`,
ADR-0010), связь с разработчиком с доставкой, подсказка на свободный текст и
guard-триггеры «протухших» кнопок (клик по старой карточке без данных в сессии
перезапускает форму, а не шлёт пустую заявку). Контракт
документа — [src/domain/flow/codec.py](../../src/domain/flow/codec.py). Проверка
исполнимости — [tests/unit/examples/test_first_bot_request_assistant.py](../../tests/unit/examples/test_first_bot_request_assistant.py)
(валидность к публикации + прогон всех путей на стабах).

### Где живёт база знаний, промт и модель

В узле `n_ai` (блок `http_request`), поле `params.body`:

- `messages[0].content` — **системный промт + база знаний литеральным текстом**
  (публичные данные, не секрет). Правишь здесь — это и есть источник фактов бота.
- `messages[1].content` — `"{user_question}"` (вопрос пользователя из `n_ask_prompt`).
- `model` — по умолчанию `openai/gpt-4o-mini`; замени на любую модель OpenRouter.
- `headers.Authorization` — `Bearer {{secret:openrouter_api_key}}`: ключ
  подставляется HTTP-клиентом на отправке из «секрета подключения» и **никогда**
  не сериализуется в тело/логи/БД (см. `process_update._resolve_secrets`).

> ⚠️ Замени демо-базу знаний на реальные данные компании. Бот отвечает **строго
> по базе** и не выдумывает — если факта нет, честно уводит к специалисту.

## Развёртывание (dev)

База — `http://127.0.0.1:8000` (см. compose). Токен бота и ключ OpenRouter —
секреты: в git/логи не кладём, живут только в `.secrets/` (gitignored).

**Шаги 1–4 локальные** (без вызовов Telegram). **Шаги 5–7 — реальные вызовы
Telegram API**, выполняются с явного согласия (политика `policy_external_api_calls=ask`).

```bash
# 1. Поднять окружение (API + PostgreSQL 16 + Redis 7)
docker compose up -d

# 2. Создать бота по уже выданному токену  → вернёт {"id": "<BOT_ID>", ...}
curl -sX POST http://127.0.0.1:8000/api/bots \
  -H 'Content-Type: application/json' \
  -d '{"name":"MetaFlowAssistantBot","platform":"telegram","token":"<BOT_TOKEN>"}'

# 3. Засеять ключ OpenRouter как секрет подключения (имя = openrouter_api_key) → 204
curl -sX PUT http://127.0.0.1:8000/api/bots/<BOT_ID>/connections/openrouter_api_key \
  -H 'Content-Type: application/json' \
  -d '{"value":"<OPENROUTER_API_KEY>"}'

# 3a. Привязать адресатов уведомлений (роли admin/developer из блоков notify) → 204.
#     chat_id — числовой id чата получателя (получатель должен один раз нажать
#     Start у бота, иначе платформа не даст боту писать первым).
curl -sX PUT http://127.0.0.1:8000/api/bots/<BOT_ID>/notifications/admin \
  -H 'Content-Type: application/json' -d '{"chat_id":"<ADMIN_CHAT_ID>"}'
curl -sX PUT http://127.0.0.1:8000/api/bots/<BOT_ID>/notifications/developer \
  -H 'Content-Type: application/json' -d '{"chat_id":"<DEV_CHAT_ID>"}'

# 4. Сохранить сценарий (оборачиваем definition; UTF-8 обязателен для кириллицы)
jq '{definition: ., name: "Умный помощник по заявкам"}' flow.definition.json \
  | curl -sX PUT http://127.0.0.1:8000/api/bots/<BOT_ID>/flow \
      -H 'Content-Type: application/json; charset=utf-8' --data-binary @-

# 5. Опубликовать  → verify_token дергает Telegram getMe (РЕАЛЬНЫЙ вызов) + BR-006
curl -sX POST http://127.0.0.1:8000/api/bots/<BOT_ID>/publish

# 6. Публичный URL вебхука через туннель (ngrok/cloudflared) и setWebhook (РЕАЛЬНЫЙ вызов):
#    URL вебхука = https://<public-host>/webhooks/telegram/<BOT_ID>
#    secret_token = значение WEBHOOK_SECRET (если задан) — Telegram вернёт его
#    в заголовке X-Telegram-Bot-Api-Secret-Token, вебхук-роут его проверяет.
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<public-host>/webhooks/telegram/<BOT_ID>&secret_token=<WEBHOOK_SECRET>"

# 7. Живой смоук: /start в Telegram → приветствие + меню → «Задать вопрос» → живой ответ.
```

## Осознанные ограничения MVP

Головная фича (AI-ответ по базе знаний + каркас + сбор заявки до подтверждения)
работает вживую. Отложено следующим этапом (ADR):

- **Доставка уведомлений — best-effort (ADR-0010).** Заявка/вопрос реально
  доставляются админу/разработчику блоком `notify`, но при сбое доставки
  (получатель заблокировал бота, роль не привязана) уведомление тихо теряется,
  а пользователь всё равно видит «принято». Гарантированная доставка (outbox +
  ретраи) и онбординг-захват chat_id (`/register_admin`) — следующий этап.
- **Хэндофф к человеку — кнопками, не по полю `status`.** Движок пока не умеет
  двухуровневый разбор JSON-ответа и `contains`/`and`/`or` в `condition`; поэтому
  AI просят отвечать плоским текстом, а под каждым ответом — кнопки
  «Оставить заявку»/«Передать разработчику». Пустой ответ ловится `condition`
  и уводит на экран специалиста.
- **ПДн — по BR-008 (ADR-0011).** Сбор имени/контакта — только после экрана
  согласия (`req_start`/`dev_start`). Стирание в этом сценарии обеспечивают
  **save-узлы-стиратели**: «Отменить» зануляет собранное немедленно (и protухшая
  «Подтвердить» после отмены не отправит заявку — guard не пустит), после
  доставки админу переменные тоже стираются. Страховочный контур платформы:
  зависшие сессии просрочиваются по `SESSION_IDLE_TTL`, завершённые/просроченные
  старше `SESSION_RETENTION_DAYS` удаляются из БД целиком фоновой чисткой.
  Вопрос к AI уходит внешнему провайдеру (OpenRouter) — prompt предупреждает
  не вводить ПДн. Редактирование формы — «Заполнить заново» (P2).
- **У `http_request` нет egress-allowlist (SSRF).** Пока контур dev-only; до
  открытого прод-доступа блок должен ходить только на разрешённые хосты.
- **Нет обрезки длины вопроса и троттлинга** AI-эндпоинта (anti-abuse) — P2.
- **AI-вызов идёт синхронно внутри вебхука** (`timeout` 20с). Для нагрузки —
  очередь/фоновая обработка.

## Портируемость на MAX

Тот же `Flow` данными публикуется и на MAX (BR-005/006): `http_request` —
server-side и платформонезависим, кнопки-`next` и меню — общие. Перед релизом
MAX сверить 6 пунктов «требует проверки» из `specs/002-platform-deep-dive/report.md`.
