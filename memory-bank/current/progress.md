---
status: active
version: "1.4"
updated: 2026-07-08
verified_commit: ""
owner: ""
---

# Статус meta-bot-core

Живое состояние проекта: что стабильно, что в работе, что сломано, где база
знаний разошлась с кодом. Агент обновляет файл в конце каждой значимой сессии
автономно (см. [../_meta/governance.md](../_meta/governance.md)). Читается
обязательно перед работой над багом — см. [../README.md](../README.md).

## Работает

<!-- Что стабильно и на что можно опираться. Крупными блоками, не по коммитам. -->

- 2026-07-06 — строгий контур CA: [.importlinter](../../.importlinter)
  (6 контрактов), CI [arch-lint](../../.github/workflows/arch-lint.yml) +
  [ci.yml](../../.github/workflows/ci.yml) (ruff/mypy/pytest, coverage ≥90%).
- 2026-07-06 — реестр ADR: 0001–0002 accepted, 0003–0008 proposed.
- 2026-07-08 — вертикальный срез бэкенда в `src/` по канону CA: domain
  (Bot/Flow/Session, инварианты BR-001/003/006), application (6 портов,
  CreateBot/PublishBot), presentation (`/health`), скелет infrastructure.
  Контур качества зелёный: ruff (ALL) · mypy strict · `lint-imports` 5/5 ·
  pytest 32 unit. Стек: Python 3.14 + uv (`uv.lock`), Dockerfile + compose
  (PG16+Redis7) — по образцу sro-agent-core.
- 2026-07-08 — прототип редактора `frontend/constructor/` (React Flow, ADR-0007).
- 2026-07-08 — хранение по ADR-0008 реализовано: ORM-модели, Pg-репозитории
  (версии Flow, оптимистический лок, единственная активная Session),
  Alembic-миграция 0001; интеграционные тесты на testcontainers (PG16) зелёные.

## В работе

<!-- Начато, но не завершено; в каком состоянии оставлено и что дальше. -->

- 2026-07-08 — ратификация ADR [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md)–[0008](../decisions/0008-persistence-model.md):
  пока proposed, ждут решения команды. Следом — `infrastructure/db` по ADR-0008
  (models/mappers/repositories, Alembic, testcontainers) и admin/webhook-роуты.

## Известные проблемы

<!-- Живые баги и ограничения, о которых надо знать до начала работы.
     Починено → строку удалить. -->

| Проблема | Влияние | Обходной путь | Issue |
|---|---|---|---|
| Нет IAM: Admin API без аутентификации; token vault — dev-файл (`.secrets/`) | Контур только для доверенной среды разработки | Auth и прод-vault — открытые вопросы active-context; порты позволяют заменить без правки ядра | — |
| Блоки open_mini_app / http_request / custom_code движком не исполняются | Сценарии с ними не публикуются (BR-006 отсекает по CapabilityMatrix v1) | Реализуются своими этапами (mini app, HTTP-порт, песочница ADR-0003) | — |

## Расхождения база↔код

<!-- Сюда агенты фиксируют найденные противоречия между документами базы и кодом
     (или между документами) — НЕ исправляя их молча, см. [../_meta/lifecycle.md](../_meta/lifecycle.md).
     Расхождение устранено (документ или код поправлен) → строку удалить. -->

- 2026-07-08 — канон портов/use case'ов ([../architecture/overview.md](../architecture/overview.md))
  не содержит `BotRepository`, `IdempotencyPort`, `SaveFlowDraftUseCase`,
  `GetBotUseCase` — добавлены кодом (Admin API/webhook их требуют); внести в
  glossary/patterns/overview при ратификации ADR-0008/0009.

## Технический долг

<!-- Только крупные пункты, влияющие на планирование. Мелочь — в issue-трекер.
     У каждого пункта — ссылка на issue и почему это долг (какое правило нарушено). -->

- 2026-07-06 — не выбрано хранилище секретов за портом `TokenVaultPort`
  (token vault) — уточнить у команды; блокирует безопасную реализацию
  BR-004/BR-007, см. [../architecture/overview.md](../architecture/overview.md).
- 2026-07-06 — не зафиксированы пороги покрытия тестами (в CI включён гейт
  ≥90% на domain/application по testing-strategy.md; ратифицировать).
- 2026-07-08 — отложено по аудиту (осознанно): (1) optimistic lock агрегата
  Bot между get() и save() — до конкурентных админ-сценариев (IAM);
  (2) seed `capability_matrix` в БД — матрицы v1 живут в адаптерах, таблица
  ждёт ратификации ADR-0005; (3) `session.flow_version_id/current_node_id`
  nullable вопреки design.md §1 — черновая сессия создаётся до первого шага.

---

<!-- Правила: записи и строки таблиц с датами YYYY-MM-DD, коротко, по факту;
     при каждом обновлении вычищать отработанное — починенное, устранённое, закрытый
     долг (история — в git); повторяющееся с известным лечением → ops/runbooks/,
     системные решения → decisions/; при содержательной правке поднимать version/updated. -->

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
