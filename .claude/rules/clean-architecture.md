---
paths:
  - "src/**"
  - ".importlinter"
  - "main.py"
---

# Строгий режим Clean Architecture — правила при работе с кодом

Ты правишь код `meta-bot-core`. Здесь границы слоёв соблюдаются строго и
проверяются машиной. Канон слоёв — `memory-bank/architecture/overview.md`,
ADR — `memory-bank/decisions/0001-clean-architecture.md` и
`0002-domain-core-and-adapters.md`.

## Направление зависимостей (нерушимо)

`presentation → application → domain`; `infrastructure` реализует порты
application/domain и подключается в composition root (`src/main.py`).

- `domain/` не импортирует НИЧЕГО из других слоёв и никаких фреймворков
  (`fastapi`, `sqlalchemy`, `aiogram`, `httpx`, `redis`, `celery`).
- `application/` импортирует только `domain` и собственные порты; наружу — только
  через `Protocol`-порты в `application/ports/`.
- `infrastructure/` и `presentation/` не импортируют друг друга; платформенные
  адаптеры `platforms/telegram` и `platforms/max` не импортируют друг друга.
- Ветвление `if platform == "telegram" / "max"` вне `infrastructure/platforms/` —
  запрещено (BR-005). Платформу выбирает `PlatformFactory`, различия скрыты за
  `BotPlatformPort` и в capability matrix (`memory-bank/architecture/patterns.md`).

## Обязательная проверка протечки слоёв

1. **До правки** прогони `lint-imports` — убедись, что стартуешь с зелёного.
2. **После правки** прогони `lint-imports` снова.
3. **Красный линтер — это дефект, который ты чинишь в этой же задаче**, а не
   помечаешь TODO и не глушишь строкой-исключением.

## Как чинить протечку (а не заглушать)

Нашёл импорт «наружу» — разверни зависимость, не пробивай границу:

- **domain потянул инфраструктуру/фреймворк** → вынеси потребность в порт
  (`Protocol` в `application/ports/`), а конкретную реализацию — в
  `infrastructure/`; домен принимает абстракцию, а не тянет реализацию.
- **application импортит infrastructure** (клиент БД, SDK платформы) → замени
  прямой импорт на порт; реализацию внедряй через конструктор use case; сборка —
  в `src/main.py`.
- **presentation ходит в БД/адаптер мимо application** → заведи/вызови use case;
  роут только транслирует HTTP↔DTO.
- **telegram импортит max (или наоборот)** → общий контракт подними в
  `BotPlatformPort`/общие DTO application; платформенное оставь в своём адаптере.
- **появился `if platform == …` в ядре** → перенеси различие в адаптер платформы
  или в capability matrix; ядро вызывает `platform.send_message(command)`.

Не можешь развернуть зависимость в рамках текущей задачи — **не мержи**: зафиксируй
`python scripts/mb_log.py discrepancy architecture/overview.md "<протечка>"`
и сообщи пользователю. Ослабление контракта (`.importlinter`) — только через ADR
с обоснованием, а не молча.

## Синхронизация с базой знаний

- Новый порт/паттерн — отрази в `memory-bank/architecture/patterns.md`.
- Новая сущность/термин — сначала в `memory-bank/domain/glossary.md`, потом в код.
- Изменил поведение из `memory-bank/domain/business-rules.md` — обнови документ
  в том же PR; правило без теста считается нереализованным.
- Меняешь сами границы слоёв — сначала ADR (`memory-bank/decisions/`), потом код.
