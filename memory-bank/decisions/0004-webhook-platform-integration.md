---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: ""
decision_status: proposed
---

# ADR-0004: Приём обновлений через webhook (не long polling)

> Черновик на ратификацию командой. `accepted` ставит владелец раздела.

## Контекст

И Telegram, и MAX предоставляют Bot API поверх HTTPS и поддерживают два способа
получать обновления: webhook (платформа шлёт HTTPS POST с событием на наш URL) и
long polling (мы опрашиваем платформу). Ограничения платформ:

- **Telegram**: пока включён webhook, `getUpdates` не используется; поддерживаемые
  порты webhook — 443, 80, 88, 8443.
- **MAX**: для production рекомендован webhook; long polling ограничен и для
  production не подходит. Дополнительно: до **19 июля 2026** нужно перевести запросы
  с `platform-api.max.ru` на `platform-api2.max.ru`, а токен передавать в заголовке
  `Authorization` (не query-параметром). Детали конфигурации —
  [../ops/configuration.md](../ops/configuration.md).

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. Long polling | Проще локально, не нужен публичный HTTPS | Не для production (особенно MAX); хуже масштабируется; лишний трафик |
| 2. **Webhook в production, long polling только для локальной отладки** | Рекомендованный обеими платформами путь; масштабируется; единый вход | Нужен публичный HTTPS-эндпоинт и валидация источника |

## Решение

- Production принимает обновления **через webhook**. Единый вход:
  `presentation/api/webhook_routes.py` с маршрутами `/webhooks/telegram/{bot_id}`
  и `/webhooks/max/{bot_id}`.
- Каждый платформенный адаптер (`infrastructure/platforms/*/webhook.py`) парсит свой
  формат update и приводит его к единой модели `IncomingEvent`; дальше приложение
  работает только с ней ([0002-domain-core-and-adapters.md](0002-domain-core-and-adapters.md)).
- Webhook-pipeline (приём → нормализация → идемпотентность → запуск сценария) общий;
  различается только парсинг. Идемпотентность приёма — через Redis.
- Long polling допустим **только** для локальной отладки, не для prod
  ([../ops/local-dev.md](../ops/local-dev.md)).
- Платформенные технические требования (порты Telegram; `platform-api2.max.ru` и
  `Authorization`-заголовок MAX; дедлайн 2026-07-19) — в
  [../ops/configuration.md](../ops/configuration.md) и в capability/клиенте адаптера,
  не в ядре.

## Последствия

**Положительные:**
- Единый масштабируемый вход, соответствующий рекомендациям обеих платформ.
- Платформенные детали приёма изолированы в адаптерах.

**Отрицательные:**
- Нужен публичный HTTPS и туннель/стенд для локальной разработки.
- Обязательная валидация источника вебхука и идемпотентность.

**Риски:**
- Пропущенная миграция MAX на `platform-api2.max.ru` до 2026-07-19 сломает интеграцию.
  Митигация: срок и хост зафиксированы в [../ops/configuration.md](../ops/configuration.md),
  задача — в [../current/active-context.md](../current/active-context.md).

## Ссылки

- [0002-domain-core-and-adapters.md](0002-domain-core-and-adapters.md) — единая модель события
- [../architecture/platform-reference.md](../architecture/platform-reference.md) — проверенные факты webhook Telegram/MAX (порты, авторизация, ретраи доставки, авто-отписка MAX после 8 ч без 200 OK)
- [../ops/configuration.md](../ops/configuration.md) — хосты, порты, токены платформ
- [../ops/local-dev.md](../ops/local-dev.md) — локальная отладка
