---
status: draft
version: "1.5"
updated: 2026-07-11
verified_commit: ""
owner: ""
---

# ADR — реестр и правила ведения

ADR (Architecture Decision Record) фиксирует одно архитектурно значимое решение:
контекст, рассмотренные варианты, само решение и его последствия. Раздел —
**append-only**: история решений не переписывается, а дополняется новыми ADR.
Это ответ базы знаний на вопрос «почему здесь так устроено».

## Когда решение требует ADR

Пиши ADR, если на любой из вопросов ответ «да»:

- [ ] Решение **дорого откатить** (миграция данных, смена протокола, публичный контракт)?
- [ ] Затрагивает **несколько модулей/слоёв** или границы между ними?
- [ ] Это **выбор технологии** (библиотека, БД, брокер, фреймворк — см. [../architecture/tech-stack.md](../architecture/tech-stack.md))?
- [ ] Это **отступление от принятых паттернов** из [../architecture/patterns.md](../architecture/patterns.md)?

Если все ответы «нет» — ADR не нужен: достаточно комментария в PR или записи
в [../current/active-context.md](../current/active-context.md).

## Именование

`NNNN-kebab-имя.md`: четырёхзначный номер по порядку + короткое имя решения
в kebab-case на английском. Пример: `0002-switch-to-postgres.md`.
Номер выдаётся при создании черновика и не переиспользуется, даже если ADR отклонён.

## Жизненный цикл (decision_status)

Статус живёт в frontmatter ADR (поле `decision_status`,
схема — [../_meta/frontmatter.md](../_meta/frontmatter.md)):

```
proposed ──> accepted ──> superseded   (заменён новым ADR)
    └──────> rejected
```

- `proposed` — черновик, вынесен на обсуждение.
- `accepted` — принято; **по существу не редактируется**. Передумали — пишем
  новый ADR, а у старого меняем только `decision_status: superseded`
  и добавляем ссылку на заменяющий (у нового — поле `supersedes`).
- `rejected` — отклонено; сохраняем как память о том, почему «нет».
- ADR не переводятся в `status: archived` — у них свой цикл
  (см. [../_meta/lifecycle.md](../_meta/lifecycle.md)).

## Кто утверждает

Статусы `accepted` / `rejected` ставит **только человек** (владелец раздела —
см. [../_meta/governance.md](../_meta/governance.md)). Агент автономно создаёт
ADR только со статусом `proposed` и сообщает об этом в ответе пользователю.

## Как создать ADR

1. Скопируй [0000-template.md](0000-template.md) в `NNNN-kebab-имя.md`
   (следующий свободный номер).
2. Заполни секции, оставь `decision_status: proposed`.
3. Добавь строку в реестр ниже и открой PR на обсуждение.
4. После решения команды человек проставляет итоговый статус
   (в ADR и в реестре) в том же PR.

## Реестр ADR

| № | Название | Статус | Дата |
|---|---|---|---|
| [0000](0000-template.md) | Шаблон ADR (не решение) | — | 2026-07-06 |
| [0001](0001-clean-architecture.md) | Clean Architecture + SOLID, строгий режим | accepted | 2026-07-06 |
| [0002](0002-domain-core-and-adapters.md) | Доменное ядро + платформенные адаптеры | accepted | 2026-07-06 |
| [0003](0003-flow-engine-blocks-and-sandbox.md) | Движок сценариев на блоках + изолированные Python-блоки | proposed | 2026-07-06 |
| [0004](0004-webhook-platform-integration.md) | Приём обновлений через webhook | proposed | 2026-07-06 |
| [0005](0005-capability-matrix.md) | Матрица возможностей платформ + единые блоки | proposed | 2026-07-06 |
| [0006](0006-mini-app-as-web-product.md) | Mini app как отдельный web-продукт с bridge | proposed | 2026-07-06 |
| [0007](0007-visual-flow-editor.md) | Визуальный редактор сценариев — React + React Flow | proposed | 2026-07-08 |
| [0008](0008-persistence-model.md) | Модель хранения: версии Flow в JSONB, Session в PG+Redis | proposed | 2026-07-08 |
| [0009](0009-max-adapter-thin-client.md) | MaxBotAdapter — тонкий httpx-клиент вместо SDK maxapi | proposed | 2026-07-08 |
| [0010](0010-notify-block-and-notification-targets.md) | Блок notify + адресаты уведомлений (роль → chat_id) | proposed | 2026-07-09 |
| [0011](0011-session-pii-retention.md) | Ретеншен и стирание ПДн сессий (BR-008) | proposed | 2026-07-10 |
| [0012](0012-message-edit-in-place.md) | Обновление отправленных сообщений (edit-in-place ответа на нажатие) | proposed | 2026-07-11 |

ADR-0001 и 0002 приняты (основа проекта); 0003–0012 — черновики на ратификацию
командой: статус `accepted` им проставляет владелец раздела
([../_meta/governance.md](../_meta/governance.md)).
