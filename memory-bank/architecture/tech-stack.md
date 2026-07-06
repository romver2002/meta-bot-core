---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: ""
---

# Технологический стек

Канонический реестр технологий meta-bot-core (Python 3.12 async · FastAPI ·
PostgreSQL 16 + SQLAlchemy 2 · Redis 7 · изолированный executor песочницы ·
TypeScript mini app; ruff / mypy / import-linter; pytest; CI — GitHub Actions).
К какому слою относится технология — [overview.md](overview.md). Крупные выборы
фиксируются через ADR — [../decisions/README.md](../decisions/README.md).

## Реестр

Статусы: `принята` — используем по умолчанию; `испытываем` — пилот в ограниченном
объёме, для нового кода нужна явная договорённость; `выводим` — новый код не пишем,
существующий мигрируем.

| Технология | Версия | Роль | Статус |
|---|---|---|---|
| Python | 3.12 | основной язык, единый async-рантайм backend | принята |
| FastAPI | — | presentation: admin API конструктора + webhook-роуты | принята |
| PostgreSQL | 16 | основное хранилище: `Bot`/`Flow`/`Session` (persistent) | принята |
| SQLAlchemy (async) | 2.x | infrastructure: доступ к БД, реализация `FlowRepository`/`SessionRepository` | принята |
| Redis | 7 | infrastructure: runtime-состояние FSM (`Session`) и идемпотентность вебхуков | принята |
| import-linter | — | контроль границ слоёв (`.importlinter`, команда `lint-imports`) | принята |
| ruff | — | стиль: форматирование + линт | принята |
| mypy | — | статическая типизация, режим strict | принята |
| pytest | — | тесты (unit + интеграционные) | принята |
| изолированный executor (sandbox) | — | infrastructure: исполнение `CustomCodeBlock` за `CodeExecutorPort` (отдельный воркер/контейнер) | испытываем |
| TypeScript + mini app bridge | — | отдельный web-продукт: mini app runtime и platform bridge (Telegram/MAX) | принята |
| GitHub Actions | — | CI: джоба `arch-lint`, тесты, проверки | принята |
| token vault | — | infrastructure: безопасное хранение `Token` за `TokenVaultPort` (конкретное хранилище — уточнить у команды) | принята |

Слой каждой технологии — по таблице слоёв в [overview.md](overview.md);
пересечение границ идёт только через порты application (см.
[patterns.md](patterns.md)). ADR по ключевым выборам: строгая Clean Architecture —
[0001](../decisions/0001-clean-architecture.md); доменное ядро + платформенные
адаптеры — [0002](../decisions/0002-domain-core-and-adapters.md); движок на блоках +
песочница Python — [0003](../decisions/0003-flow-engine-blocks-and-sandbox.md);
приём обновлений через webhook — [0004](../decisions/0004-webhook-platform-integration.md);
capability matrix — [0005](../decisions/0005-capability-matrix.md); mini app как
web-продукт — [0006](../decisions/0006-mini-app-as-web-product.md).

**Версии в столбце «Версия»** проставлены только там, где мажор зафиксирован каноном;
остальные пинуются lock-файлом (см. ниже), а не этой таблицей. **Токены и init-данные
mini app — секреты**: живут только в token vault, не в БД в открытом виде и не в базе
знаний ([security.md](security.md)).

## Версии

- Точные версии зависимостей фиксируются lock-файлом: `poetry.lock` или `uv.lock` —
  выбор менеджера зависимостей (poetry / uv) уточнить у команды; после выбора этот
  пункт и строку CI обновить.
- Обновление мажорной версии — отдельный PR + обновление соответствующей строки реестра.
- Уязвимости зависимостей отслеживаются в CI (разумный дефолт — `pip-audit`;
  конкретный инструмент, dependabot / renovate / pip-audit, уточнить у команды).

## Добавление новой зависимости

Прежде чем добавлять библиотеку, ответь письменно (в описании PR или в ADR):

1. Решается ли задача стандартной библиотекой или уже принятым стеком?
2. Проект живой? Поддержка, частота релизов, известные CVE.
3. Лицензия допустима? Разрешены пермиссивные лицензии (MIT, Apache-2.0, BSD, ISC);
   copyleft (GPL/AGPL) — только с явного согласия; точный список уточнить у команды.
4. В какой слой попадает? **Зависимостей в `domain`-слое нет** — domain не импортирует
   фреймворки и внешние библиотеки (FastAPI, SQLAlchemy, SDK платформ, httpx, redis);
   правило проверяется import-linter'ом ([overview.md](overview.md)).
5. Насколько глубоко врастёт — какова цена отказа через год?

Процедура:

- Мелкая dev-зависимость (линтер, утилита для тестов) — обычный PR с обоснованием
  в описании.
- Всё, что влияет на архитектуру или прод-рантайм (фреймворк, БД, брокер, крупная
  библиотека, платформенный адаптер), — через ADR по шаблону
  [../decisions/0000-template.md](../decisions/0000-template.md); статус `accepted`
  ставит человек (см. [governance](../_meta/governance.md)).
- После принятия — строка в реестр выше (обычно со статусом `испытываем`), с указанием
  слоя из [overview.md](overview.md).
- Границы слоёв проверяются автоматически: до и после правки `src/` прогоняется
  `lint-imports` (локально, в pre-commit и в CI-джобе
  [arch-lint](../../.github/workflows/arch-lint.yml)); протокол при протечке —
  [.claude/rules/clean-architecture.md](../../.claude/rules/clean-architecture.md).
