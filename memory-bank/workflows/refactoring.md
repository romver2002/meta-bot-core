---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: ""
---

# Процесс: рефакторинг

Пошаговый процесс для агента. Протокол сессии — в [../../AGENTS.md](../../AGENTS.md).
Рефакторинг не меняет наблюдаемое поведение; если поведение меняется —
это фича ([new-feature.md](new-feature.md)) или баг ([bug-fix.md](bug-fix.md)).

В meta-bot-core рефакторинг чаще всего затевают, чтобы **устранить протечку слоя**
(например, `if platform == …` или импорт SDK в `application`/`domain`) или снять
дублирование в адаптерах платформ. Разворот зависимости ради восстановления границ —
это цель рефакторинга, а не побочный эффект.

## 0. Перед началом прочитай

- [ ] [../current/active-context.md](../current/active-context.md) — не пересекается ли рефакторинг с текущими работами (риск конфликтов).
- [ ] [../architecture/patterns.md](../architecture/patterns.md) — целевые паттерны (порт + адаптер, `PlatformFactory`, DTO границ) и анти-паттерны.
- [ ] [../architecture/overview.md](../architecture/overview.md) — слои `domain → application → infrastructure/presentation` и границы, которые нельзя нарушить.
- [ ] [../architecture/testing-strategy.md](../architecture/testing-strategy.md) — чем будет доказана эквивалентность поведения (pytest).
- [ ] [../decisions/README.md](../decisions/README.md) — нет ли ADR, который уже фиксирует текущее устройство (Clean Architecture — ADR 0001, доменное ядро + адаптеры — ADR 0002); тогда менять его можно только новым ADR.

## 1. Зафиксируй цель и границы

Запиши до первого изменения кода (в задаче/PR и в
[../current/active-context.md](../current/active-context.md)):

1. **Цель** — какую конкретную проблему устраняем: дублирование, протечка слоя
   (импорт наружу, ветвление по платформе вне `infrastructure/platforms/`),
   god-object, лишняя связность. «Сделать красиво» — не цель. Разворот зависимости
   для устранения протечки (вынос за порт, инверсия направления) — легитимная цель.
2. **Границы** — какие модули/каталоги трогаем (например, `src/application/use_cases/`
   и `src/infrastructure/platforms/telegram|max/`).
3. **Что НЕ трогаем** — явный список: публичные контракты admin API конструктора и
   webhook-роутов (`/webhooks/telegram/{bot_id}`, `/webhooks/max/{bot_id}`), схема БД
   без отдельной миграции, поведение, соседние модули «за компанию». Постоянные
   запретные зоны проекта: контракты портов (`BotPlatformPort` и др.) и файл границ
   `.importlinter` — меняются только новым ADR; token vault и mini app как отдельный
   web-продукт — вне зоны этого рефакторинга (точный перечень уточнить у команды).
4. Критерий остановки: цель достигнута → стоп, даже если видно «ещё улучшения».
   Новые идеи — отдельной записью в [../current/progress.md](../current/progress.md).

## 2. Тесты до

1. Прогони весь набор (pytest) — базовая линия должна быть зелёной. Красные тесты —
   сначала разберись с ними (это может быть чужой баг → [bug-fix.md](bug-fix.md)).
2. Зафиксируй исходную зелёную границу слоёв: `lint-imports` (import-linter, контракт
   [../../.importlinter](../../.importlinter)) до правок — чтобы отличать протечку,
   которую устраняем, от новой, которую можно случайно внести.
3. Затронутый код слабо покрыт → добавь characterization-тесты, фиксирующие
   текущее поведение, до любых изменений.

## 3. Шаги малыми порциями

1. Один шаг = одно механическое преобразование (переименование, extract,
   перемещение, инверсия зависимости, вынос платформенной ветки за `BotPlatformPort`).
2. После каждого шага: сборка успешна, `pytest` и `lint-imports` зелёные. Красное
   после шага — откати шаг, а не чини «по пути».
3. Коммиты — по шагам, по [../architecture/git-workflow.md](../architecture/git-workflow.md);
   смешивать рефакторинг с функциональными изменениями в одном коммите нельзя.

## 4. Сверка с архитектурой

- [ ] Направление зависимостей после рефакторинга — только внутрь
  (`presentation → application → domain`, infrastructure реализует порты);
  проверено `lint-imports`, сверено по [../architecture/overview.md](../architecture/overview.md).
- [ ] Устраняемая протечка (импорт наружу, `if platform == …` вне
  `infrastructure/platforms/`) действительно снята разворотом зависимости, а не
  заглушена игнор-строкой в `.importlinter`; протокол —
  [../../.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md),
  CI-джоба [../../.github/workflows/arch-lint.yml](../../.github/workflows/arch-lint.yml).
- [ ] Не появился анти-паттерн из [../architecture/patterns.md](../architecture/patterns.md).
- [ ] Меняются сами границы слоёв, контракт порта или вводится/выводится паттерн →
  **черновик ADR** по [../decisions/0000-template.md](../decisions/0000-template.md)
  (`decision_status: proposed`); статус accepted ставит человек —
  см. [../_meta/governance.md](../_meta/governance.md). До согласования
  ограничься минимальным объёмом изменений.

## 5. Обнови базу и current/

- [ ] Рефакторинг изменил то, что описано в architecture/ (структура слоёв, дерево
  каталогов, паттерн, стек) → обнови [../architecture/patterns.md](../architecture/patterns.md)
  и/или [../architecture/overview.md](../architecture/overview.md) в том же PR.
- [ ] [../current/active-context.md](../current/active-context.md) — итог: что сделано, что осталось за границами.
- [ ] [../current/progress.md](../current/progress.md) — отложенные идеи улучшений, найденные расхождения.

## Definition of Done

- [ ] Цель и границы были зафиксированы до начала; границы не нарушены.
- [ ] Наблюдаемое поведение не изменилось: весь набор тестов (pytest) зелёный, новых функциональных изменений нет.
- [ ] `lint-imports` зелёный до и после; протечка (если чинили) устранена разворотом зависимости, а не игнором.
- [ ] Сверка с patterns.md и overview.md пройдена; при смене границ/контрактов портов — черновик ADR создан и озвучен.
- [ ] Затронутые architecture-доки и `current/` обновлены; `python scripts/validate_memory_bank.py` проходит.

## Пример

Цель: `SendMessageUseCase` (application) содержит `if platform == "telegram"` при
сборке кнопок — платформенная логика протекла в application (нарушение BR-005 и
правила зависимостей; ловится `lint-imports` и ревью).
Границы: `src/application/use_cases/`, `src/infrastructure/platforms/telegram|max/`;
НЕ трогаем контракт `BotPlatformPort`, admin/webhook API, схему БД, mini app.
Тесты до: characterization-тест «узел `show_buttons` → адаптеру уходит единая
модель `Button`, а не платформенная разметка».
Шаги: (1) убрать ветвление, вызвав построение кнопки у `BotPlatformPort`;
(2) реализовать платформенный маппинг в `TelegramBotAdapter` и `MaxBotAdapter`;
(3) выбор адаптера оставить за `PlatformFactory` в composition root (`src/main.py`).
Итог: зависимость развёрнута — application снова не знает о платформе; это цель
рефакторинга, а не побочка. `lint-imports` зелёный, поведение не изменилось.
Границы слоёв не менялись (восстановлены) → новый ADR не нужен; понадобилось бы
расширить сам контракт `BotPlatformPort` — сначала черновик ADR. Пример порта в
architecture/patterns.md уже есть, current/ обновлён.
</content>
</invoke>
