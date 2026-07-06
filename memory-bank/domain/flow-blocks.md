---
status: active
version: "1.0"
updated: 2026-07-07
verified_commit: ""
owner: ""
---

# Каталог блоков сценария (узлов Flow)

Операционная спецификация шагов сценария. Сущности `Flow`/`Node`/`Trigger`/`Button`
и их инварианты — в [domain-model.md](domain-model.md); термины — в
[glossary.md](glossary.md). Почему блоки, а Python — только «аварийный выход» —
ADR [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md). Почему блоки
единые, а различия платформ — в матрице — ADR
[0005](../decisions/0005-capability-matrix.md) и
[../architecture/platform-reference.md](../architecture/platform-reference.md).

Блок — это **данные** (тип + параметры), а не код. Движок (`RunFlowUseCase`)
исполняет граф блоков; пользовательский Python исполняется только через
`CodeExecutorPort` в песочнице (BR-004). Блоки — единые для всех платформ; в
платформенное представление их переводит адаптер за `BotPlatformPort` (BR-005).

## Триггеры (вход в сценарий)

`Trigger` запускает сценарий или ветку. Типы:

| Тип | Когда срабатывает | Данные |
|---|---|---|
| `/start` | команда старта бота | — |
| `text` | входящее текстовое сообщение (точное совпадение/паттерн) | текст |
| `callback` | нажатие inline-кнопки (`ButtonClicked`) | payload кнопки |
| `mini_app_result` | mini app вернул результат (`MiniAppOpened` → результат) | данные из mini app (после валидации init data, BR-007) |

Инвариант публикации: у `Flow` есть хотя бы один входной `Trigger` (BR-001).

## Блоки (узлы `Node`)

Колонка «Порт/реализация» — через что блок выходит во внешний мир (границы —
[../architecture/overview.md](../architecture/overview.md)). Все блоки, кроме
`custom_code`, платформонезависимы; доступность на платформе — по `CapabilityMatrix`
(BR-006), см. матрицу в [../architecture/platform-reference.md](../architecture/platform-reference.md).

| Тип узла | Что делает | Ключевые параметры | Порт / реализация |
|---|---|---|---|
| `send_message` | отправляет пользователю текст (с переменными сценария) | `text` (шаблон с подстановками), опц. вложение | `BotPlatformPort.send_message` → `SendMessageUseCase` |
| `show_buttons` | отправляет сообщение с кнопками (`Button`) | `text`, список `Button` (подпись + действие) | `BotPlatformPort` (маппер кнопок в адаптере) |
| `ask` | задаёт вопрос и ждёт ответ пользователя, сохраняя его в переменную | `prompt`, `save_as` (имя переменной), опц. валидация | движок + `SessionRepository` (перевод FSM в ожидание) |
| `condition` | ветвление по условию над переменными сценария | выражение/сравнение, ветви `true`/`false` | движок (без внешних вызовов) |
| `open_mini_app` | показывает кнопку запуска mini app, привязанного к боту | ссылка на `MiniApp` (HTTPS, BR-003) | `BotPlatformPort.build_mini_app_button` (Telegram `WebAppInfo` / кнопка MAX) |
| `save` | сохраняет данные в состояние/во внешнюю систему | ключ, значение/маппинг | `SessionRepository` (переменные) или порт хранилища |
| `http_request` | вызывает внешний HTTP-API и кладёт ответ в переменные | метод, URL, заголовки, маппинг ответа | инфраструктурный HTTP-клиент за портом (не в ядре) |
| `custom_code` | исполняет пользовательский Python-блок как чистую функцию | `code_id`/версия, `input_mapping`, `output_mapping` | `CodeExecutorPort` → песочница; `run(context) -> dict` (BR-004) |

## Кнопки (`Button`)

Единая модель: подпись + действие. Действия: `open_mini_app` (запуск mini app),
`callback` (payload → триггер `callback`), `url` (внешняя HTTPS-ссылка),
`next` (переход к узлу того же `Flow`). В платформенное представление
(`InlineKeyboardButton`/`WebAppInfo` у Telegram; кнопка/ссылка у MAX) переводит
адаптер — в ядре платформенных типов нет.

## Правила каталога

- Новый тип блока = строка в этой таблице + тип в `Node`
  ([domain-model.md](domain-model.md)) + реализация в движке/порте + тест
  ([../architecture/testing-strategy.md](../architecture/testing-strategy.md)) в одном PR.
- Различие платформ по блоку выражается **данными** в `CapabilityMatrix`, а не
  `if platform == …` (BR-005). Блок, недоступный на платформе бота, не предлагается
  в конструкторе и отклоняется при публикации (BR-006).
- Платёжный и иной platform-specific функционал оформляется отдельными блоками с
  ограниченной доступностью, но тоже за портом (ADR
  [0005](../decisions/0005-capability-matrix.md)).
- `custom_code` — расширение, не замена блоков: базовые действия (сообщение, кнопки,
  условие, mini app, сохранение) делаются блоками, Python — для сложной логики
  (расчёты, скоринг, нестандартная валидация), ADR
  [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md).
