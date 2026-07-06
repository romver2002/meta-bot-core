# meta-bot-core

Доменное ядро конструктора **сценариев** чат-ботов и mini app для мессенджеров
(Telegram, MAX; далее VK/WhatsApp как плагины). Это **движок исполняемых сценариев
+ платформенные адаптеры**, а не «универсальный бот» и не «генератор ботов»: ядро
не знает, что такое Telegram или MAX, — платформы подключаются за портами.

Формула: **Bot Constructor = Flow Engine + State Machine + Platform Adapters + Mini App Runtime.**

Конструктор не регистрирует платформенного бота (аккаунт, модерация и лимиты — на
стороне платформы), а управляет поведением уже зарегистрированного бота, связываясь
по токену.

## С чего начать

- **Агентам и разработчикам** — вход в проект: [AGENTS.md](AGENTS.md) (карточка +
  обязательный протокол) и индекс базы знаний [memory-bank/README.md](memory-bank/README.md).
- **Что за продукт и зачем** — [memory-bank/product/vision.md](memory-bank/product/vision.md).
- **Архитектура** (Clean Architecture, строгий режим) —
  [memory-bank/architecture/overview.md](memory-bank/architecture/overview.md).
- **Интеграция с платформами** (проверенные факты Telegram/MAX) —
  [memory-bank/architecture/platform-reference.md](memory-bank/architecture/platform-reference.md).
- **Ключевые решения** — [memory-bank/decisions/README.md](memory-bank/decisions/README.md) (ADR 0001–0006).

## Стек

Python 3.12 (async) · FastAPI · PostgreSQL 16 + SQLAlchemy 2 · Redis 7 ·
изолированный executor для Python-блоков · TypeScript mini app (отдельный
web-продукт). Реестр — [memory-bank/architecture/tech-stack.md](memory-bank/architecture/tech-stack.md).

## Строгий режим Clean Architecture

Границы слоёв (`presentation → application → domain`; `infrastructure` реализует
порты) проверяются машиной. Протечка слоя ломает сборку.

```bash
lint-imports                          # границы слоёв (контракт .importlinter)
python scripts/validate_memory_bank.py  # валидатор базы знаний
```

Контракт — [.importlinter](.importlinter); протокол исправления протечек —
[.claude/rules/clean-architecture.md](.claude/rules/clean-architecture.md);
CI-гейт — [.github/workflows/arch-lint.yml](.github/workflows/arch-lint.yml).

## База знаний

`memory-bank/` — git-версионируемая база знаний, которую агенты перечитывают в
каждой сессии (развёрнута из внутреннего шаблона memory bank). Правила ведения —
[memory-bank/_meta/](memory-bank/_meta/lifecycle.md); чувствительные операции — по
[memory-bank/_meta/policy.md](memory-bank/_meta/policy.md) (наивысший приоритет).
