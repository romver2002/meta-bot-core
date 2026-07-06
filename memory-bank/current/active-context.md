---
status: active
version: "1.1"
updated: 2026-07-07
verified_commit: ""
owner: ""
---

# Активный контекст meta-bot-core

Живой снимок «что происходит прямо сейчас». Агент читает его в начале каждой
сессии (протокол — в [../../AGENTS.md](../../AGENTS.md)) и обновляет в конце
каждой значимой сессии — автономно, без PR-ревью. Это единственный раздел
с такой автономией, см. [../_meta/governance.md](../_meta/governance.md).

## Текущий фокус

<!-- 1–3 пункта: что делаем сейчас и ПОЧЕМУ именно это (ссылка на roadmap/issue). -->

- 2026-07-06 — заведён проект meta-bot-core из шаблона базы знаний: наполняем
  `memory-bank/` реальным содержимым. Фундамент — строгая Clean Architecture
  ([../architecture/overview.md](../architecture/overview.md)); границы слоёв держит
  import-linter ([../../.importlinter](../../.importlinter)) в CI-джобе arch-lint
  ([../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml)).
- 2026-07-06 — заложены доменные знания конструктора сценариев ботов Telegram/MAX
  (сущности, порты, бизнес-правила): [../domain/glossary.md](../domain/glossary.md),
  [../domain/business-rules.md](../domain/business-rules.md).

## Последние решения и договорённости

<!-- Список с датами, ~10 строк. Старше пары недель — в decisions/ или удалить. -->

- 2026-07-06 — приняты (accepted) ADR-0001 «Clean Architecture + SOLID, строгий режим»
  ([../decisions/0001-clean-architecture.md](../decisions/0001-clean-architecture.md)) и ADR-0002
  «Доменное ядро + платформенные адаптеры» ([../decisions/0002-domain-core-and-adapters.md](../decisions/0002-domain-core-and-adapters.md)) — фундамент.
- 2026-07-06 — ADR-0003..0006 (движок на блоках + песочница, webhook, capability matrix,
  mini app как web-продукт) — черновики `proposed`, ждут ратификации командой
  ([../decisions/README.md](../decisions/README.md)).
- 2026-07-07 — решено: интеграцию MAX делаем **сразу на `platform-api2.max.ru`**
  (проект greenfield); старый `platform-api.max.ru` не используем, «миграции» нет.
  Токен MAX — в заголовке `Authorization`; в доверенные добавляется сертификат Минцифры
  ([../architecture/platform-reference.md](../architecture/platform-reference.md),
  [../ops/configuration.md](../ops/configuration.md)).

## Следующие шаги

<!-- Конкретные ближайшие действия, у каждого понятен результат. Не бэклог. -->

- 2026-07-06 — вынести ADR-0003–0006 на решение команды; статус accepted/rejected
  проставляет человек ([../_meta/governance.md](../_meta/governance.md)).
- 2026-07-06 — начать MVP end-to-end: Admin UI → Webhook Gateway → Flow Engine →
  Message Dispatcher → Mini App ([../product/roadmap.md](../product/roadmap.md)).
- 2026-07-07 — `MaxBotAdapter` пишем сразу под `platform-api2.max.ru` (токен в
  `Authorization`, не в query); старый хост не поддерживаем. Внешний дедлайн
  платформы 2026-07-19 нас не блокирует — стартуем уже на v2.

## Открытые вопросы к команде

<!-- Вопрос блокирует работу? Получен ответ → удалить, решение зафиксировать выше. -->

- 2026-07-06 — менеджер зависимостей и lock-файл: poetry или uv? (уточнить у команды).
- 2026-07-06 — хранилище секретов за `TokenVaultPort` (token vault) — какое? (уточнить у команды).
- 2026-07-06 — пороги покрытия тестами в CI — какой минимум? (уточнить у команды).

---

Правила ведения файла — [../_meta/lifecycle.md](../_meta/lifecycle.md).
