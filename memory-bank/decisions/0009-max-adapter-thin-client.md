---
status: active
version: "1.0"
updated: 2026-07-08
verified_commit: ""
owner: ""
decision_status: proposed
---

# ADR-0009: MaxBotAdapter — тонкий httpx-клиент вместо SDK maxapi

> Черновик на ратификацию командой. `accepted` ставит владелец раздела.

## Контекст

Для `MaxBotAdapter` рассматривался SDK [maxapi](https://github.com/love-apples/maxapi)
(указан Романом 2026-07-08): живой (v1.2.1, 202★), MIT, async, стиль aiogram —
Dispatcher/Router/фильтры/middleware, транспорт aiohttp. Нашему адаптеру нужен
только тонкий клиент: `verify_token`, `send_message`, парсинг update в
`IncomingEvent` — маршрутизацию делает наш Flow Engine (ADR-0003), приём — наш
webhook-вход (ADR-0004). Критично: greenfield сразу на `platform-api2.max.ru`,
токен в `Authorization` (решение 2026-07-07).

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. maxapi как основа адаптера | Готовые типы/методы MAX API | Dispatcher/Router дублируют Flow Engine; aiohttp рядом с каноничным httpx; хост/эволюция API вне нашего контроля |
| 2. **Тонкий httpx-клиент** (принят) | Ровно нужная поверхность; канон httpx; полный контроль хоста platform-api2 и заголовка Authorization | Методы/схемы MAX сверяем с dev.max.ru сами |
| 3. maxapi только как справочник типов | Меньше чтения доков | То же, что 2, плюс риск устаревшего референса |

## Решение

`MaxBotAdapter` — **тонкий httpx-клиент** (`infrastructure/platforms/max/`):
`GET /me` (проверка токена), `POST /messages` (отправка + inline_keyboard),
парсер `bot_started | message_created | message_callback` → `IncomingEvent`.
maxapi остаётся справочником при сверке схем API. Пересмотр — если поверхность
MAX-вызовов вырастет на порядок (медиа, файлы, чаты).

## Последствия

**Положительные:** нет дублирующего фреймворка и второй HTTP-библиотеки;
различия платформ остаются данными (BR-005). **Отрицательные:** схемы MAX API
поддерживаем сами (источник — dev.max.ru + platform-reference.md).
**Риски:** дрейф API MAX — ловится интеграционным контуром и сверкой
platform-reference.md при правках адаптера.

## Ссылки

- [../architecture/platform-reference.md](../architecture/platform-reference.md) — хосты, webhook, форматы
- [0002](0002-domain-core-and-adapters.md), [0004](0004-webhook-platform-integration.md), [0005](0005-capability-matrix.md)
- Реализация: `src/infrastructure/platforms/max/{adapter,webhook}.py`
