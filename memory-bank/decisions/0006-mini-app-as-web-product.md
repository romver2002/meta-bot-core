---
status: active
version: "1.1"
updated: 2026-07-11
verified_commit: ""
owner: ""
decision_status: proposed
---

# ADR-0006: Mini app как отдельный web-продукт с platform bridge

> Черновик на ратификацию командой. `accepted` ставит владелец раздела.

## Контекст

Mini app возможны и в Telegram, и в MAX, но это **не** «одинаковый фронт в разных
мессенджерах». Это общий web-продукт, у которого запуск, авторизация, кнопки, шаринг
и platform bridge — разные:

- **Telegram Mini Apps** запускаются из кнопки, меню бота, inline-кнопки, прямой
  ссылки, attachment menu; Telegram передаёт в mini app данные пользователя, сессию,
  start parameter и даёт JS API `Telegram.WebApp`.
- **MAX mini app** работает только внутри MAX, подключается к конкретному чат-боту,
  требует HTTPS URL и использует MAX Bridge / `window.WebApp`. Без чат-бота mini app
  в MAX добавить нельзя; файлы размещаются на HTTPS-хостинге, URL указывается в
  настройках бота, после чего в чате появляется кнопка запуска (BR-003).

Бизнес-логика mini app (корзина, профиль, каталог) общая; различаются только bridge
и авторизация.

## Рассмотренные варианты

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. Отдельный фронт под каждую платформу | Простая ментальная модель | Дублирование корзины/каталога/профиля; расхождение поведения |
| 2. Один фронт с `if platform` в компонентах | Меньше кода на старте | Platform-детали протекают в бизнес-логику фронта |
| 3. **Общее ядро mini app + platform bridge за интерфейсом** | Логика одна; платформенное за `MiniAppPlatform` | Нужны реализации bridge под каждую платформу |

## Решение

- Mini app — **отдельный web-продукт** (TypeScript), а не часть backend'а. Общая
  логика (`core/cart`, `core/profile`, `core/catalog`) не знает о платформе.
- Платформа — за интерфейсом `MiniAppPlatform` (`getInitData`, `getUser`, `close`,
  `share`, `openLink`) с реализациями `TelegramMiniAppPlatform` (через
  `Telegram.WebApp`), `MaxMiniAppPlatform` (через MAX Bridge / `window.WebApp`) и
  `BrowserMiniAppPlatform` (для локальной разработки).
- **Init data валидируется на backend'е** по правилам платформы (подпись Telegram /
  данные MAX Bridge) до того, как данным пользователя доверяют (BR-007). На стороне
  meta-bot-core это порт mini app-авторизации, реализуемый в
  `infrastructure/platforms/*/mini_app_auth.py`.
- Mini app «живёт» как приложение, привязанное к платформенному боту (для MAX это
  обязательное условие), и возвращает результат выбора в backend, который продолжает
  сценарий ([0003-flow-engine-blocks-and-sandbox.md](0003-flow-engine-blocks-and-sandbox.md)).

## Размещение и хранение (дополнение черновика, 2026-07-11)

Ответ на вопрос владельца «где и как хранить архитектуру mini app»:

- **Код** — отдельный пакет монорепозитория `frontend/miniapp/` (свой
  `package.json`, свой build), появится вместе с первым сценарием, которому
  он нужен (витрина-магазин из roadmap). Заводить пустой каркас заранее не
  стали (YAGNI); `frontend/constructor/` — другой продукт (редактор), их не
  смешиваем.
- **Деплой** — статические файлы на HTTPS-хостинге/CDN (требование MAX —
  только HTTPS), НЕ внутри Python-движка. Backend движка отдаёт mini app
  только два контракта: `POST /api/bots/{id}/miniapp/auth` (валидация init
  data, BR-007) и `POST .../miniapp/result` (результат -> триггер
  `mini_app_result`).
- **Связь с ботом — только данными**: у `Bot` в БД хранится HTTPS-URL
  привязанного mini app (`PUT /api/bots/{id}/miniapp`); движок рисует кнопку
  запуска (`open_mini_app`), ничего mini-app-специфичного в ядро не течёт.
- **Данные mini app** (корзина, каталог, заказы) — отдельный bounded context
  (Shop и т.п.) со своим хранилищем; в `Session.variables` движка попадает
  только результат, который сценарий явно сохраняет (и он живёт по BR-008).

## Последствия

**Положительные:**
- Одна бизнес-логика mini app для всех платформ; платформенное изолировано в bridge.
- Backend доверяет пользователю mini app только после валидации init data.

**Отрицательные:**
- Нужны отдельные реализации bridge и mini app-авторизации под каждую платформу.
- Отдельный деплой-контур фронта (HTTPS-хостинг).

**Риски:**
- Ошибка валидации init data = подмена пользователя. Митигация: валидация обязательна
  на backend'е, покрыта тестами; изменения — апрув владельца `architecture/`
  ([../architecture/security.md](../architecture/security.md)).

## Ссылки

- [0002-domain-core-and-adapters.md](0002-domain-core-and-adapters.md) — платформа как адаптер
- [0003-flow-engine-blocks-and-sandbox.md](0003-flow-engine-blocks-and-sandbox.md) — возврат результата в сценарий
- [../domain/business-rules.md](../domain/business-rules.md) — BR-003, BR-007
- [../architecture/security.md](../architecture/security.md) — валидация init data
