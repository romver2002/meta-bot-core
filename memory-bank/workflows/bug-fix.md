---
status: active
version: "1.1"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Процесс: исправление бага

Пошаговый процесс для агента. Протокол сессии — в [../../AGENTS.md](../../AGENTS.md).
Если баг горит в продакшене и подходит под критерии hotfix —
переключись на [hotfix.md](hotfix.md).

## 0. Перед началом прочитай

- [ ] [../current/progress.md](../current/progress.md) — не известен ли баг уже (разделы «Известные проблемы», «Расхождения»).
- [ ] [../current/active-context.md](../current/active-context.md) — не связан ли баг с текущими работами.
- [ ] [../architecture/overview.md](../architecture/overview.md) — карта слоёв для локализации.
- [ ] [../ops/observability.md](../ops/observability.md) — где смотреть логи/метрики, если баг из эксплуатации.

## 1. Воспроизведи

1. Собери факты: точные шаги, ожидаемое/фактическое поведение, окружение, версия.
2. Добейся минимального воспроизведения локально (по [../ops/local-dev.md](../ops/local-dev.md)).
3. Не воспроизводится — не гадай, спроси у человека: точные входные данные,
   окружение и его конфигурация, время/частота, логи или ID запроса.
   Для бага из эксплуатации ID запроса — из webhook-роута (`/webhooks/telegram/{bot_id}`,
   `/webhooks/max/{bot_id}`); токены и init-данные mini app в отчёты не тащи (секреты).

## 2. Локализуй слой

Определи, где дефект, двигаясь от симптома внутрь (карта слоёв —
[../architecture/overview.md](../architecture/overview.md)):

- **Адаптер платформы** (`infrastructure/platforms/telegram|max/`) — неверный
  маппинг update ↔ `IncomingEvent`, сериализация ответа, вызов Telegram/MAX API,
  разбор callback, валидация init data mini app.
- **Инфраструктура** (`infrastructure/db|queue|code_executor/`) — репозиторий
  (`FlowRepository`/`SessionRepository`), идемпотентность вебхука (Redis),
  песочница `CodeExecutorPort`, token vault.
- **Use case** (`application/`) — неверная оркестровка (`ProcessUpdateUseCase`,
  `PublishBotUseCase`, `CreateBotUseCase`…), порядок вызовов
  портов, обработка ошибок.
- **Домен** (`domain/`) — неверный инвариант `Flow`/`Bot`/`Node` или бизнес-правило.
  Сверь с [../domain/business-rules.md](../domain/business-rules.md): баг в коде
  или в правиле (BR-NNN)?
- **Композиция/конфигурация** — не тот адаптер собран в `PlatformFactory`
  (`src/main.py`), неверная переменная окружения
  (см. [../ops/configuration.md](../ops/configuration.md)).

Симптом «работает в Telegram, ломается в MAX (или наоборот)» — сперва
[../architecture/platform-reference.md](../architecture/platform-reference.md)
и `CapabilityMatrix`: возможно, различие платформ, а не дефект логики. Ветвление
`if platform == …` вне `infrastructure/platforms/` — это сам по себе баг (BR-005).

## 3. Сначала падающий тест

1. Напиши регрессионный тест, воспроизводящий баг, на уровне локализованного слоя
   (уровень — по [../architecture/testing-strategy.md](../architecture/testing-strategy.md);
   домен и use case — юнит, адаптеры и песочница — интеграционный).
2. Убедись, что он **падает** по той же причине, что и баг. Только потом фикс.

## 4. Исправь

1. Минимальное исправление в **локализованном** слое; попутный рефакторинг —
   отдельной задачей через [refactoring.md](refactoring.md). Правило зависимостей
   не нарушай: наружу — только через порт, платформенные различия — в адаптере.
2. Тест из шага 3 зелёный, весь набор тестов (`pytest`) зелёный.
3. Правил `src/` → прогони `lint-imports` (import-linter, контракт
   [../../.importlinter](../../.importlinter); та же джоба в CI —
   [../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)):
   фикс не должен протечь через границу слоя или между платформами. Красный линтер
   чини разворотом зависимости, а не заглушкой/игнором
   ([../../.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md)).
4. Проверь соседние места с тем же паттерном ошибки — баг редко живёт один
   (второй адаптер платформы, соседний use case, другой тип `Node`).

## 5. Сверь документацию с кодом

- Баг возник из-за расхождения база↔код (документ обещал одно, код делал другое)?
  Действуй по правилу о противоречиях из [../../AGENTS.md](../../AGENTS.md):
  зафиксируй в [../current/progress.md](../current/progress.md) (раздел «Расхождения»)
  и сообщи человеку — не правь стабильные доки молча.
- Фикс изменил поведение или бизнес-правило (BR-NNN) — обнови base-доки в том же PR:
  [../domain/business-rules.md](../domain/business-rules.md),
  [../domain/glossary.md](../domain/glossary.md),
  [../architecture/overview.md](../architecture/overview.md) или
  [../ops/configuration.md](../ops/configuration.md), — с упоминанием в описании PR.
  Меняешь суть принятого (accepted) ADR — не задним числом: новый ADR
  ([../decisions/README.md](../decisions/README.md)).

## 6. Обнови current/ (и ранбук при инциденте)

- [ ] [../current/progress.md](../current/progress.md) — баг закрыт; расхождения — в свой раздел.
- [ ] [../current/active-context.md](../current/active-context.md) — если баг менял текущий фокус.
- [ ] Баг дошёл до инцидента в продакшене → ранбук по
  [../ops/runbooks/incident-template.md](../ops/runbooks/incident-template.md)
  (реестр — [../ops/runbooks/README.md](../ops/runbooks/README.md)).

## Definition of Done

- [ ] Баг воспроизведён (или получено подтверждение человека о шагах).
- [ ] Есть регрессионный тест, падавший до фикса и зелёный после; весь набор зелёный.
- [ ] Правил `src/` → `lint-imports` проходит (границы слоёв и платформ не протекли).
- [ ] Расхождения база↔код зафиксированы в progress.md и озвучены; при смене
      поведения/BR обновлены base-доки в том же PR.
- [ ] `current/` обновлён; при инциденте — ранбук создан/дополнен.
- [ ] `python scripts/validate_memory_bank.py` проходит, если базу правили.

## Пример

Баг: бот публикуется, хотя в его сценарии (`Flow`) нет ни одного `Trigger`, —
пользователи не могут его запустить. Воспроизведён публикацией `Bot` с валидным
токеном, но пустым по триггерам `Flow`. Локализация: инвариант нарушен в домене —
`Bot.publish` (`src/domain/bot/entities.py`) не проверял наличие хотя бы одного
триггера, чего требует BR-001; слой — domain. Падающий тест
(`tests/unit/bot/test_bot_publish.py`): публикация с `Flow` без `Trigger` →
ожидается доменная ошибка; до фикса тест был красным (публикация проходила).
Фикс: инвариант добавлен в `Bot.publish`; `lint-imports`, весь набор тестов и
валидатор базы — зелёные. Это расхождение база↔код (business-rules.md обещал
правило, код его не соблюдал): поведение теперь соответствует BR-001, доки менять
не пришлось, но факт зафиксирован в progress.md (раздел «Расхождения») и озвучен
человеку.
