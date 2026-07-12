---
status: active
version: "1.3"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Технологический стек

Канонический реестр технологий meta-bot-core (Python 3.14 async · FastAPI ·
PostgreSQL 16 + SQLAlchemy 2 · Redis 7 · изолированный executor песочницы ·
TypeScript 7 + Vite 8 mini app; uv · ruff / mypy / import-linter; pytest/Vitest;
CI — GitHub Actions).
К какому слою относится технология — [overview.md](overview.md). Крупные выборы
фиксируются через ADR — [../decisions/README.md](../decisions/README.md).

## Политика актуальности стека (решение владельца, Роман, 2026-07-11)

Используем **самый современный стабильный стек, актуальный на 2026-07-11**,
и держим его актуальным дальше:

- новые зависимости берутся в последних стабильных версиях;
- при обновлении инструментов и библиотек по умолчанию поднимаемся до последних
  стабильных (точные версии фиксирует lock-файл `uv.lock`);
- устаревшие API и паттерны не тащим «по привычке»: экосистема ушла вперёд —
  идём за ней (через ADR, если выбор архитектурно значим);
- «старое, потому что знакомое» — не аргумент; аргументы — стабильность релиза,
  поддержка, совместимость с реестром ниже.

## Реестр

Статусы: `принята` — используем по умолчанию; `испытываем` — пилот в ограниченном
объёме, для нового кода нужна явная договорённость; `выводим` — новый код не пишем,
существующий мигрируем.

| Технология | Версия | Роль | Статус |
|---|---|---|---|
| Python | 3.14 | основной язык, единый async-рантайм backend (решение Романа 2026-07-08, равнение на sro-agent-core) | принята |
| uv | — | менеджер зависимостей и версий Python; lock-файл `uv.lock`, `.python-version` | принята |
| FastAPI | — | presentation: admin API конструктора + webhook-роуты; конфигурация — Pydantic `Settings` на pydantic-settings (`src/infrastructure/config.py`) | принята |
| PostgreSQL | 16 | основное хранилище: `Bot`/`Flow`/`Session` (persistent) | принята |
| SQLAlchemy (async) | 2.x | infrastructure: доступ к БД (async-драйвер — asyncpg), реализация `FlowRepository`/`SessionRepository` | принята |
| Alembic | — | infrastructure: миграции схемы PG (`alembic.ini` + `migrations/`), применяются на старте контейнера (`compose.yaml`) | испытываем¹ |
| Redis | 7 | infrastructure: идемпотентность вебхуков; hot-FSM `Session` — запланирован ADR-0008, пока не реализован (сессии в PG) | принята |
| httpx | — | infrastructure: HTTP-клиент за `HttpClientPort` (`src/infrastructure/http/`) | принята |
| import-linter | — | контроль границ слоёв (`.importlinter`, команда `lint-imports`) | принята |
| ruff | — | стиль: форматирование + линт | принята |
| mypy | — | статическая типизация, режим strict | принята |
| pytest | — | тесты (unit + интеграционные) | принята |
| изолированный executor (sandbox) | — | infrastructure: исполнение `CustomCodeBlock` за `CodeExecutorPort` (отдельный воркер/контейнер) — запланирован ADR-0003 (proposed), реализация не начата: существует только порт `CodeExecutorPort` | испытываем |
| Node.js | 24 LTS | build/test runtime фронтендов; production mini app — статические файлы без Node.js | принята |
| TypeScript | 7.x | строго типизированный mini app runtime и platform bridge | принята |
| Vite | 8.x | dev-server и production-сборка `frontend/miniapp/`; assets для HTTPS/CDN | принята |
| Vitest | 4.x | unit-тесты API-клиента, controller и bridge-адаптеров mini app | принята |
| GitHub Actions | — | CI: джоба `arch-lint`, тесты, проверки | принята |
| token vault | — | infrastructure: безопасное хранение `Token` за `TokenVaultPort` (конкретное хранилище — уточнить у команды) | принята |

¹ Перевод Alembic в «принята» — при ратификации
[ADR-0008](../decisions/0008-persistence-model.md).

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

- Точные версии зависимостей фиксируются lock-файлом `uv.lock` (менеджер — uv;
  решение Романа 2026-07-08). Floor-версии (`>=`) — в `pyproject.toml`,
  точные пины держит lock.
- Frontend mini app фиксирует точные версии в `frontend/miniapp/package-lock.json`
  (npm); мажоры Node.js/TypeScript/Vite/Vitest закреплены в реестре выше.
- Обновление мажорной версии — отдельный PR + обновление соответствующей строки реестра.
- Аудит уязвимостей зависимостей в CI пока не настроен; планируется
  (кандидаты: `pip-audit` / dependabot — выбор за командой).

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
