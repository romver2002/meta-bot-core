---
status: active
version: "1.3"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Бизнес-правила meta-bot-core

Реестр правил поведения системы, продиктованных бизнесом (не техникой).
Каждое правило имеет номер BR-NNN, источник, место реализации и тест.
Термины — из [glossary.md](glossary.md); инварианты структуры данных —
в [domain-model.md](domain-model.md), сюда не дублируются. Контексты, к которым
относятся правила, — в [bounded-contexts.md](bounded-contexts.md).

Канон конструктора: `Bot Constructor = Flow Engine + State Machine + Platform
Adapters + Mini App Runtime`. Конструктор управляет поведением уже
зарегистрированного платформенного бота по токену, а не создаёт бота за
пользователя, — отсюда и правила ниже.

## Правила ведения реестра

- **Изменение бизнес-правила = обновление строки + кода + теста в одном PR.**
  Правило без теста считается нереализованным.
- Номера BR-NNN выдаются по порядку и **никогда не переиспользуются**.
- Отменённое правило не удаляется: статус → `отменено`, в колонке «Правило»
  кратко почему и чем заменено (например, «заменено BR-014»).
- Источник обязателен: имя человека/роли, документ или ссылка на решение
  ([../decisions/README.md](../decisions/README.md)). «Так исторически сложилось» —
  не источник; такое правило помечай `под вопросом` и выясняй у владельца
  раздела ([../_meta/governance.md](../_meta/governance.md)).
- Нашёл в коде поведение, похожее на бизнес-правило, но его нет в реестре —
  это расхождение: действуй по [../_meta/lifecycle.md](../_meta/lifecycle.md).

## Реестр

| ID | Правило | Статус | Источник | Где реализовано | Тест |
|---|---|---|---|---|---|
| BR-001 | Бот (`Bot`) публикуется только при валидном токене зарегистрированного платформенного бота и непустом сценарии (`Flow`) с хотя бы одним триггером (`Trigger`) | активно | Проектный дизайн 2026-07-06; [ADR-0002](../decisions/0002-domain-core-and-adapters.md) | `src/domain/bot/entities.py::Bot.publish` | `tests/unit/bot/test_bot_publish.py` |
| BR-002 | Конструктор не создаёт платформенный аккаунт бота и не обходит модерацию и лимиты платформы (MAX: обязательная модерация; лимиты — 5 ботов для организации/ИП, 2 для самозанятого). `Bot` заводится только по уже выданному токену | активно | Проектный дизайн 2026-07-06; [ADR-0002](../decisions/0002-domain-core-and-adapters.md) | Политика создания `Bot` только по токену — `CreateBotUseCase` | `tests/unit/bot/test_create_bot_policy.py` — уточнить у команды |
| BR-003 | Mini app (`MiniApp`) привязан к боту и вне чат-бота не существует (в MAX — только внутри чат-бота); URL mini app — только HTTPS | активно | Проектный дизайн 2026-07-06; [ADR-0006](../decisions/0006-mini-app-as-web-product.md) | `src/domain/bot/entities.py::MiniApp` | `tests/unit/bot/test_mini_app.py` — уточнить у команды |
| BR-004 | Python-блок (`CustomCodeBlock`) исполняется как чистая функция `run(context) -> dict` в изоляции: таймаут 1–3 c, лимит памяти и размера ответа, без доступа к ФС, env, токенам и БД, сеть — только по whitelist; блок версионируется, ошибки логируются | запланировано (реализован только контракт порта) | Проектный дизайн 2026-07-06; [ADR-0003](../decisions/0003-flow-engine-blocks-and-sandbox.md) | `CodeExecutorPort` (`src/application/ports/code_executor.py`) — контракт; изолированный executor не реализован | интеграционный, ожидается при реализации: `tests/integration/code_executor/test_sandbox_isolation.py` |
| BR-005 | Бизнес-логика сценария не ветвится по платформе: `if platform == …` вне `infrastructure/platforms/` запрещён — платформа выбирается фабрикой и скрыта за `BotPlatformPort` | активно | Проектный дизайн 2026-07-06; [ADR-0002](../decisions/0002-domain-core-and-adapters.md), [ADR-0005](../decisions/0005-capability-matrix.md) | `PlatformFactory` + `BotPlatformPort` | `lint-imports` (import-linter, [`.importlinter`](../../.importlinter)) + ревью; CI-джоба [arch-lint](../../.github/workflows/arch-lint.yml) |
| BR-006 | Возможность или блок, недоступные на платформе бота по `CapabilityMatrix`, не предлагаются в конструкторе и отклоняются при публикации сценария | активно | Проектный дизайн 2026-07-06; [ADR-0005](../decisions/0005-capability-matrix.md) | `CapabilityMatrix` + `Flow.validate_for_publication` | `tests/unit/flow/test_flow_validate_capabilities.py` |
| BR-007 | Init data mini app валидируется на backend по правилам платформы (подпись Telegram / данные MAX Bridge) до того, как данные пользователя считаются доверенными | активно | Проектный дизайн 2026-07-06; [ADR-0006](../decisions/0006-mini-app-as-web-product.md) | `platforms/{telegram,max}/mini_app_auth.py` + общие `webapp_signature.py` и `mini_app_identity.py` за `BotPlatformPort.validate_init_data`; use case `AuthenticateMiniAppUseCase` | `tests/unit/platforms/test_webapp_signature.py`, `tests/unit/platforms/test_mini_app_identity.py`, `tests/unit/api/test_api_miniapp.py` |
| BR-008 | Минимизация ПДн сессий: переменные сценария живут не дольше сессии (завершение/просрочка стирает их); завершённые/просроченные сессии старше срока хранения удаляются целиком, включая `external_user_id`/`external_chat_id`; сбор ПДн в сценарии — только после явного согласия пользователя (экран согласия — данные Flow) | активно | Обращение с ПДн (152-ФЗ), решение 2026-07-10; [ADR-0011](../decisions/0011-session-pii-retention.md) | `Session.complete/expire` (домен) + `PurgeExpiredSessionsUseCase` за `SessionRetentionPort` + фоновая чистка composition root | `tests/unit/application/test_purge_expired_sessions.py`, `tests/integration/test_pg_repositories.py::test_session_retention_expires_idle_and_deletes_finished` |

Точные имена тестовых модулей с пометкой «уточнить у команды» — разумный дефолт
по конвенции BR-001 (`tests/<уровень>/<область>/test_<правило>.py`); закрепляются
в том же PR, что и реализация правила.

## Как распознать бизнес-правило

Наводящие вопросы:

- Может ли это требование измениться решением бизнеса/продукта без смены
  технологии? Да → бизнес-правило, сюда. Нет (таймауты, ретраи, порты, хосты API,
  лимиты БД) → не сюда.
- Есть ли условие вида «нельзя X, если/после Y», «при X всегда Y»,
  «размер/срок/сумма ограничены Z»? Это типовые формы правил (ср. BR-001, BR-003,
  BR-006).
- Валидация формата сама по себе (HTTPS-схема URL) — обычно не бизнес-правило;
  а вот «mini app без бота не существует» — правило (BR-003, и инвариант в
  [domain-model.md](domain-model.md); здесь фиксируется номером, реализация — одна).

**Технические ограничения платформ — не бизнес-правила и сюда не попадают.**
Работа MAX сразу на `platform-api2.max.ru` (greenfield, старый `platform-api.max.ru`
не использовался) и передача токена в заголовке `Authorization`, порты вебхука Telegram
(443/80/88/8443), приём обновлений через webhook вместо long polling — это
конфигурация и интеграция платформы. Их место —
[../ops/configuration.md](../ops/configuration.md) и
[ADR-0004](../decisions/0004-webhook-platform-integration.md). Признак: такое
ограничение меняется при смене платформы/протокола, а не решением бизнеса.
Токены ботов и init-данные mini app — секреты и в реестр правил не выносятся
(см. [../architecture/security.md](../architecture/security.md)).

## Чек-лист при добавлении/изменении правила

- [ ] Формулировка — одним предложением, в терминах глоссария, проверяемая?
- [ ] Источник указан и при необходимости подтверждён?
- [ ] Реализация — в домен-слое (сущность/политика), а не размазана
      по контроллерам ([../architecture/overview.md](../architecture/overview.md))?
- [ ] Тест назван так, что из имени видно правило, и падает при его нарушении?
- [ ] Затронутые строки реестра, код и тесты — в одном PR?
