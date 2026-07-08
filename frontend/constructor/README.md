# Конструктор сценариев — актуальный редактор Flow

Визуальный редактор сценариев ботов **meta-bot-core** на React + React Flow.
Редактор собирает `Flow` как данные, сохраняет черновик через API конструктора и отдаёт
его Flow Engine на исполнение.

## Запуск

```bash
cd frontend/constructor
npm install
npm run dev      # http://127.0.0.1:5173
```

Dev-server проксирует `/api` и `/healthchecks` на `http://127.0.0.1:8000`, поэтому
FastAPI можно держать на стандартном локальном порту без CORS-настройки. Сборка:
`npm run build`.

## Что поддержано сейчас

- Палитра Engine v1: `send_message`, `show_buttons`, `ask`, `condition`,
  `open_mini_app`, `save`, `http_request`; `custom_code` показан как будущий
  disabled-блок, потому что текущая `CapabilityMatrix` его не публикует.
- Актуальный стартовый шаблон: «умный помощник по заявкам» с меню, AI-ответом
  через `http_request`, веткой `error`, mini app loop и формой заявки из цепочки
  `ask`.
- Настройка `trigger.config`: `text.config.pattern`, `callback.config.payload`.
- `http_request` сериализуется как backend-контракт: `headers`, `body`,
  `response_map` — JSON-объекты, `timeout` — число, outcomes `next`/`error`.
- Кнопки `Button`: `label`, `action`, `target`; для `next` target выбирается из
  узлов Flow, для `url`/`open_mini_app` требуется HTTPS.
- Панель «Боты и публикация»: `POST /api/bots`, `PUT /api/bots/{id}/flow` с `row_version`,
  `POST /publish`, `PUT /miniapp`, `PUT /connections/{name}`.
- JSON drawer показывает ровно `definition`, который уходит в `SaveFlowRequest`.
- Палитра и правая рабочая панель закрываются/открываются из topbar; справа есть
  вкладки «Настройки» и «Публикация», а формы публикации разбиты на раскрываемые
  секции. На узких экранах панели работают как overlay-drawer поверх холста.

Токены ботов и connection secrets вводятся только в password-поля и не попадают в
Flow JSON.

## Ограничения

- Редактор пока не загружает `definition` из backend: `GET /api/bots/{id}` отдаёт
  карточку бота без Flow JSON.
- Publish вызывает backend-проверки, включая platform token verification; живые
  вызовы платформ остаются под проектной политикой.
- `custom_code`, платежи, notify/outbox, egress allowlist для `http_request` и
  продовый IAM остаются отдельными этапами.
