---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: ""
---

# Процесс: новая фича

Пошаговый процесс для агента. Протокол сессии (что читать всегда, как обновлять
базу) — в [../../AGENTS.md](../../AGENTS.md), здесь только специфика фичи.

## 0. Перед началом прочитай

- [ ] [../current/active-context.md](../current/active-context.md) — не конфликтует ли фича с текущим фокусом.
- [ ] [../domain/domain-model.md](../domain/domain-model.md) и [../domain/business-rules.md](../domain/business-rules.md) — какие сущности (`Bot`, `Flow`, `Node`, `Trigger`, `Button`, `MiniApp`, `Session`) и правила (BR-001…BR-007) задевает фича.
- [ ] [../domain/glossary.md](../domain/glossary.md) — термины из формулировки задачи; незнакомый термин = вопрос человеку.
- [ ] [../domain/bounded-contexts.md](../domain/bounded-contexts.md) — в каком контексте живёт фича (Constructor / FlowExecution / PlatformIntegration / MiniApp / CodeExecution) и что этому контексту запрещено.
- [ ] [../architecture/overview.md](../architecture/overview.md) и [../architecture/patterns.md](../architecture/patterns.md) — куда фича ложится по слоям и через какие порты пересекает границы.
- [ ] [../product/roadmap.md](../product/roadmap.md) — если непонятен приоритет или контекст «зачем» (MVP: Admin UI → Webhook Gateway → Flow Engine → Message Dispatcher → Mini App).

## 1. Уточни требования

Не начинай кодить, пока нет ответов (спроси у человека, чего не хватает):

1. Кто пользователь фичи и какой сценарий она закрывает?
2. Какие граничные случаи и что считается ошибкой (валидация, конфликты, лимиты)?
3. Есть ли новые бизнес-правила? Их источник (человек/документ)?
4. Что явно НЕ входит в объём (out of scope)?
5. Как поймём, что фича работает (наблюдаемый критерий приёмки)?

Отдельно для meta-bot-core уточни на входе:

- Затрагивает ли фича различия платформ (Telegram/MAX)? Тогда это `CapabilityMatrix`
  и адаптеры, а не ветвление в бизнес-логике (BR-005, BR-006).
- Работает ли фича с токенами или init-данными mini app? Это секреты — только через
  `TokenVaultPort`/валидацию на backend, не в логах и не в БД в открытом виде (BR-007).

## 2. Крупная фича → spec-kit

Фича крупная, если верно хотя бы одно: задевает несколько bounded context связанными
изменениями протокола/данных, вводит новый агрегат, требует больше ~3 новых use case
или миграцию данных. Порог — разумный дефолт, уточнить у команды.

- Для крупной фичи используем spec-kit — прогони цепочку `/speckit.specify` →
  `/speckit.plan` → `/speckit.tasks` (наличие и настройка тулинга — уточнить у команды).
  Артефакты живут в `specs/NNN-<фича>/` в корне репозитория. Это **одноразовые наряды**
  под конкретную фичу: в memory-bank их **не переносить** — база хранит устоявшиеся
  факты, spec — рабочий артефакт.
- После мержа фичи перенеси из spec в базу только то, что стало постоянным знанием:
  принятые архитектурные решения → [../decisions/](../decisions/README.md) (ADR),
  описание архитектуры/слоёв → [../architecture/](../architecture/overview.md),
  статус и итоги → [../current/progress.md](../current/progress.md). Сам каталог
  `specs/NNN-*` остаётся рабочим следом и в базу не копируется.
- Нет spec-kit → зафиксируй ответы шага 1 (уточнение требований) в описании PR.
- Мелкая фича: достаточно ответов из шага 1, spec-kit не нужен.

## 3. Реализация по слоям (изнутри наружу)

Сначала определи слой каждого изменения по таблице слоёв в
[../architecture/overview.md](../architecture/overview.md) — Clean Architecture,
строгий режим, зависимости только внутрь: presentation → application → domain,
infrastructure реализует порты.

1. **Домен (`src/domain/`)** — сущности, value objects, инварианты, доменные события.
   Без импортов наружу и без фреймворков.
   - Новый термин? **Сначала внеси его в [../domain/glossary.md](../domain/glossary.md)**
     (имя класса/поля обязано совпадать с колонкой «Имя в коде»), только потом пиши код.
   - Новое поведение/ограничение? Это бизнес-правило: заведи `BR-NNN` в
     [../domain/business-rules.md](../domain/business-rules.md) (следующий свободный
     номер, со ссылкой на источник/ADR) **и сразу напиши тест на него**.
   - Новая сущность/агрегат? Опиши в [../domain/domain-model.md](../domain/domain-model.md).
   - Никакого `if platform == …` в домене — платформа сюда не проникает.
2. **Use case (`src/application/`)** — сценарий и порты к внешнему миру. Опирайся на
   существующие use case канона: `CreateBotUseCase`, `PublishBotUseCase`,
   `ProcessUpdateUseCase`, `RunFlowUseCase`, `SendMessageUseCase`, `OpenMiniAppUseCase`,
   `ExecuteNodeUseCase`.
   - Нужен новый порт или паттерн взаимодействия? **Сначала опиши его в
     [../architecture/patterns.md](../architecture/patterns.md)** (и в разделе портов
     глоссария), затем объяви как `Protocol` в `application/ports/`. Канонические порты:
     `BotPlatformPort`, `FlowRepository`, `SessionRepository`, `TokenVaultPort`,
     `CodeExecutorPort`, `FileStoragePort`.
   - Знания о конкретной БД/HTTP/SDK и ветвлений по платформе здесь быть не должно.
3. **Адаптеры (`src/infrastructure/`)** — реализации портов: `platforms/telegram/`,
   `platforms/max/` за `BotPlatformPort`; `db/` (SQLAlchemy) для `FlowRepository`/
   `SessionRepository`; `code_executor/` (песочница) для `CodeExecutorPort`; token vault
   за `TokenVaultPort`. Платформенные различия живут **только здесь** и в
   `CapabilityMatrix`; выбор платформы делает `PlatformFactory` (BR-005). Адаптер одной
   платформы не импортирует другой (`telegram` ⇎ `max`).
4. **Композиция (`src/main.py`)** — единственный composition root: DI, регистрация
   адаптеров в `PlatformFactory`, маршруты FastAPI (`api/admin_routes.py`,
   `api/webhook_routes.py`).

Новое архитектурно значимое решение — черновик ADR по
[../decisions/0000-template.md](../decisions/0000-template.md), на согласование команды.

**Арх-линт обязателен (строгий режим).** До и после правок в `src/` прогоняй
`lint-imports` (import-linter, контракт [../../.importlinter](../../.importlinter);
в pre-commit и в CI-джобе [arch-lint](../../.github/workflows/arch-lint.yml)).
Нашёл протечку слоя — **чини сразу** (вынеси зависимость за порт, разверни направление
через интерфейс) по [.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md);
**не заглушай линтер** игнор-строкой. Не чинится в рамках задачи — не мержи: зафиксируй
в [../current/progress.md](../current/progress.md) и сообщи.

## 4. Тесты

По [../architecture/testing-strategy.md](../architecture/testing-strategy.md) (pytest):
домен и use case покрываются обязательно, адаптеры — по стратегии проекта (пороги
покрытия — уточнить у команды). Каждое новое `BR-NNN` сопровождается тестом. Для
`CustomCodeBlock` и mini app-авторизации нужны интеграционные тесты (BR-004, BR-007).
Прогони весь набор, не только новые тесты.

## 5. Обнови базу знаний

- [ ] Новые бизнес-правила → [../domain/business-rules.md](../domain/business-rules.md).
- [ ] Новые термины → [../domain/glossary.md](../domain/glossary.md).
- [ ] Новые сущности/агрегаты → [../domain/domain-model.md](../domain/domain-model.md).
- [ ] Новые порты/паттерны или сдвиг границ → [../architecture/patterns.md](../architecture/patterns.md) / [../architecture/overview.md](../architecture/overview.md).
- [ ] База обновляется **в том же PR**, что и код: изменение без синхронизации md не считается завершённым.
- [ ] Правила правок (version, SSoT, расхождения) — по [../../AGENTS.md](../../AGENTS.md), не дублируются здесь.

## 6. Обнови current/

- [ ] [../current/active-context.md](../current/active-context.md) — статус фичи, открытые вопросы, договорённости.
- [ ] [../current/progress.md](../current/progress.md) — что сделано, что осталось, найденные расхождения.

## Definition of Done

- [ ] Ответы на вопросы шага 1 получены и учтены (для крупной фичи — spec в `specs/NNN-*/`).
- [ ] Код по слоям CA, направление зависимостей не нарушено; `lint-imports` зелёный.
- [ ] Нет `if platform == …` вне `infrastructure/platforms/`.
- [ ] Тесты написаны и зелёные (весь набор); каждое новое `BR-NNN` покрыто.
- [ ] Затронутые доки базы обновлены в том же PR (шаг 5), `python scripts/validate_memory_bank.py` проходит.
- [ ] `current/` обновлён (шаг 6).
- [ ] Коммит/PR — только по явной просьбе человека, по [../architecture/git-workflow.md](../architecture/git-workflow.md).

## Пример

Фича «Действие кнопки `url` — открыть внешнюю ссылку». Уточнили граничный случай
(вопрос 2): разрешаем только HTTPS-ссылки, `http` отклоняем при публикации. Фича мелкая
— нового агрегата, нового use case и миграций нет, изменения в адаптерах механические
(маппинг за `BotPlatformPort`), поэтому spec-kit не нужен, хотя задеты контексты
Constructor и PlatformIntegration.

- **Термин** сначала в glossary.md: действие кнопки `url` у `Button` (Constructor).
- **Домен**: расширяем действие `Button` значением `url`, инвариант «URL только HTTPS»
  (по аналогии с `MiniApp`, BR-003); новое ограничение оформляем как следующий свободный
  `BR-NNN` в business-rules.md со ссылкой на ADR
  [0006-mini-app-as-web-product](../decisions/0006-mini-app-as-web-product.md) и пишем
  юнит-тест на инвариант.
- **Доступность на платформе**: отражаем кнопку-ссылку в `CapabilityMatrix`; недоступная
  на платформе бота возможность отклоняется при публикации (BR-006).
- **Адаптеры**: маппинг в нативную кнопку в `TelegramBotAdapter` и `MaxBotAdapter` за
  `BotPlatformPort` — без ветвления в бизнес-логике (BR-005).
- **Арх-линт**: `lint-imports` до и после правок `src/` — зелёный.
- **Тесты** по testing-strategy.md: юнит на инвариант HTTPS и на валидацию по
  `CapabilityMatrix`, интеграционный на маппинг адаптера.
- **База**: правило HTTPS → business-rules.md, термин «действие `url`» → glossary.md,
  запись возможности → capability matrix; current/ обновлён, статус — «готово к ревью».
