---
status: active
version: "1.1"
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

- 2026-07-06 — база знаний развёрнута из шаблона: структура memory-bank
  (product/, domain/, architecture/, ops/, decisions/, workflows/, current/,
  _meta/) на месте, индекс [../README.md](../README.md) актуален.
- 2026-07-06 — строгий контур Clean Architecture заведён: контракт
  [../../.importlinter](../../.importlinter) (layers presentation→application→domain,
  forbidden для domain, independence платформ), CI-джоба
  [arch-lint](../../.github/workflows/arch-lint.yml) и протокол исправления
  протечек [clean-architecture.md](../../.claude/rules/clean-architecture.md).
- 2026-07-06 — реестр ADR заполнен: [0001](../decisions/0001-clean-architecture.md)
  и [0002](../decisions/0002-domain-core-and-adapters.md) приняты (accepted),
  0003–0008 заведены как proposed.
- 2026-07-08 — вертикальный срез бэкенда в `src/` по канону CA: domain
  (Bot/Flow/Session, инварианты BR-001/003/006), application (6 портов,
  CreateBot/PublishBot), presentation (`/health`), скелет infrastructure.
  Контур качества зелёный: ruff (ALL) · mypy strict · `lint-imports` 5/5 ·
  pytest 32 unit. Стек: Python 3.14 + uv (`uv.lock`), Dockerfile + compose
  (PG16+Redis7) — по образцу sro-agent-core.
- 2026-07-08 — прототип визуального редактора `frontend/constructor/`
  (React + React Flow, ADR-0007): сборка и dev-сервер проверены.

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
| `infrastructure/db` не реализован (ADR-0008 proposed), presentation — только `/health` | Сквозной путь Admin UI→webhook→движок пока не работает; Flow живёт в состоянии редактора | Юнит-контур (domain/application) полный и зелёный; интеграция — следующий этап | — |

## Расхождения база↔код

<!-- Сюда агенты фиксируют найденные противоречия между документами базы и кодом
     (или между документами) — НЕ исправляя их молча, см. [../_meta/lifecycle.md](../_meta/lifecycle.md).
     Расхождение устранено (документ или код поправлен) → строку удалить. -->

- 2026-07-08 — канонический список портов ([../architecture/overview.md](../architecture/overview.md),
  glossary) не содержит `BotRepository`, но `CreateBotUseCase`/`PublishBotUseCase`
  требуют персистенцию агрегата `Bot` — порт добавлен в
  `src/application/ports/bot_repository.py`; внести в glossary/patterns
  при ратификации [ADR-0008](../decisions/0008-persistence-model.md).

## Технический долг

<!-- Только крупные пункты, влияющие на планирование. Мелочь — в issue-трекер.
     У каждого пункта — ссылка на issue и почему это долг (какое правило нарушено). -->

- 2026-07-06 — не выбрано хранилище секретов за портом `TokenVaultPort`
  (token vault) — уточнить у команды; блокирует безопасную реализацию
  BR-004/BR-007, см. [../architecture/overview.md](../architecture/overview.md).
- 2026-07-06 — не зафиксированы пороги покрытия тестами (разумный дефолт —
  ≥80% на domain/application, уточнить у команды).

---

<!-- Правила: записи и строки таблиц с датами YYYY-MM-DD, коротко, по факту;
     при каждом обновлении вычищать отработанное — починенное, устранённое, закрытый
     долг (история — в git); повторяющееся с известным лечением → ops/runbooks/,
     системные решения → decisions/; при содержательной правке поднимать version/updated. -->

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
