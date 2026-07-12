# Mini App runtime

Отдельный TypeScript web-продукт для Telegram Mini Apps и MAX mini app. Общий
runtime не знает деталей платформ: их скрывают адаптеры `MiniAppPlatform`.

Каркас намеренно не содержит витрину, корзину или другую предметную логику. Он
проверяет сквозной путь: bridge → backend-валидация init data (BR-007) → отправка
результата `mini_app_result` → явное закрытие пользователем.

## Запуск

Нужен Node.js 24 LTS. Установка и проверки:

```bash
cd frontend/miniapp
npm install
npm run dev
npm test
npm run build
```

`build` выполняет strict typecheck, production-сборку и проверяет gzip-бюджеты:
JavaScript ≤ 64 КиБ, CSS ≤ 16 КиБ, HTML ≤ 8 КиБ. Каркас не имеет runtime npm-
зависимостей; platform bridge загружается динамически и только для текущего
мессенджера. Хешированные assets можно долго кэшировать на CDN, а `index.html`
выдавать с revalidate/no-cache.

Локальный адрес: `http://127.0.0.1:5174/?bot_id=<uuid>`. В обычном браузере это
безопасный preview: backend-auth и отправка результата не выполняются, потому что
подписанного платформой init data нет.

Vite проксирует `/api` на `http://127.0.0.1:8000`. Для отдельного HTTPS-хостинга
задайте `VITE_API_BASE_URL=https://api.example.com` при сборке и разрешите origin
mini app в явном CORS allowlist backend. Wildcard и credentials не требуются.

## Контракт запуска

URL, привязанный к боту, содержит его внутренний UUID:

```text
https://miniapp.example.com/?bot_id=<uuid>
```

`bot_id` не является секретом. Init data берётся только из bridge:

- Telegram: точная строка `window.Telegram.WebApp.initData`;
- MAX: точная внутренняя строка `window.WebApp.initData` (`WebAppData`), без
  внешних `WebAppPlatform` и `WebAppVersion`.

Runtime вызывает:

```text
POST /api/bots/{bot_id}/miniapp/auth
{"init_data":"<raw bridge initData>"}

POST /api/bots/{bot_id}/miniapp/result
{"init_data":"<raw bridge initData>","result":{"action":"confirmed"}}
```

Backend повторно проверяет подпись при отправке результата; auth endpoint не
выдаёт browser-сессию или bearer token.

## Bridge

Загрузчик определяет платформу по launch-параметрам fragment и подключает только
нужный официальный script:

- `https://telegram.org/js/telegram-web-app.js`;
- `https://st.max.ru/js/max-web-app.js`.

MAX bridge не имеет подтверждённых аналогов `ready()`/`expand()` и универсального
`close()` во всех клиентах. Поэтому lifecycle-вызовы feature-detected: `ready()`
для MAX — no-op, а кнопка закрытия показывается только при наличии `close()`.

## Производительность интерфейса

- без React, UI-kit, web-fonts и других runtime-зависимостей;
- один небольшой JS entry, системный шрифт и CSS без изображений;
- повторные auth/result запросы блокируются контроллером;
- анимации используют только transform/opacity и отключаются через
  `prefers-reduced-motion`;
- Browser preview не загружает Telegram/MAX bridge и не обращается к backend;
- production assets используют относительные пути и подходят для HTTPS/CDN.

## Безопасность

- init data не попадает в URL, storage, DOM, логи или тексты ошибок;
- `initDataUnsafe.user` может использоваться только как недоверенная UI-подсказка;
- доверенная идентичность появляется лишь после ответа backend;
- API-клиент не отражает наружу `detail` backend и отправляет запросы без cookies;
- Browser adapter не подделывает платформенную подпись и не обходит BR-007.
