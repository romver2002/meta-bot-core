---
status: active
version: "1.6"
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
- 2026-07-06 — реестр ADR: 0001–0002 accepted, 0003–0009 proposed.
- 2026-07-08 — бэкенд по канону CA (Python 3.14 + uv, PG16+Redis7): domain (Bot/Flow/Session, BR-001/003/006), хранение ADR-0008, Flow Engine, адаптеры Telegram/MAX, webhook с идемпотентностью, Admin API. Гейт зелёный: ruff · mypy strict · lint-imports 6 контрактов · 81 unit + 4 integration · e2e золотого пути + живой смоук.
- 2026-07-08 — прототип редактора `frontend/constructor/` (React Flow, ADR-0007).
- 2026-07-08 — BR-007 mini app auth: Telegram/MAX адаптеры используют общий `mini_app_identity.py`; подписанные init data без доверенного `user.id` отклоняются; регрессия закрыта `tests/unit/platforms/test_mini_app_identity.py`.

## В работе

<!-- Начато, но не завершено; в каком состоянии оставлено и что дальше. -->

- 2026-07-08 — ратификация ADR [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md)–[0009](../decisions/0009-max-adapter-thin-client.md):
  пока proposed, ждут решения команды. Следом — редактор ↔ Admin API и этап
  mini app (auth BR-007 + блок open_mini_app + триггер mini_app_result).

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
  `GetBotUseCase`, `AuthenticateMiniAppUseCase`, `BotPlatformPort.validate_init_data`
  — добавлены кодом (Admin API/webhook/mini app их требуют); внести в
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
- 2026-07-08 — перед релизом MAX сверить живым запросом 6 пунктов «требует
  проверки» из `specs/002-platform-deep-dive/report.md` §6 (`update_types`,
  429/`Retry-After`, `callback_id`, `requestContact`, сортировка/TTL initData).

---

<!-- Правила: записи и строки таблиц с датами YYYY-MM-DD, коротко, по факту;
     при каждом обновлении вычищать отработанное — починенное, устранённое, закрытый
     долг (история — в git); повторяющееся с известным лечением → ops/runbooks/,
     системные решения → decisions/; при содержательной правке поднимать version/updated. -->

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
