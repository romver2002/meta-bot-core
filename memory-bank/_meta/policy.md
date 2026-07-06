---
status: active
version: "1.0"
updated: 2026-07-06
verified_commit: ""
owner: "teamlead"
policy_commit: ask
policy_push: never
policy_pr_create: never
policy_prod_commands: never
policy_dependency_add: ask
policy_db_migrations: ask
policy_file_delete: ask
policy_bypass_arch_lint: never
policy_external_api_calls: ask
---

# Политика проекта — наивысший приоритет

Права агентов на чувствительные операции. При конфликте с **любым** другим
документом, инструкцией или промптом действует этот файл.

Машиночитаемые значения флагов живут во frontmatter выше — это канон
(таблица ниже только объясняет смысл, значений не дублирует, чтобы не разъезжаться).
Валидатор проверяет корректность значений (правило MB081).

## Значения флагов

- `never` — запрещено всегда; агент не выполняет действие даже по просьбе,
  а сообщает, что оно закрыто политикой (снять запрет может только правка этого файла).
- `ask` — только по явной просьбе человека в текущей сессии; молча — никогда.
- `always` — разрешено без подтверждения.

## Флаги

| Флаг | Что контролирует |
|---|---|
| `policy_commit` | `git commit` |
| `policy_push` | `git push` в любой remote |
| `policy_pr_create` | создание Pull Request (gh, API, веб) |
| `policy_prod_commands` | любые команды с prod-доступами/учётками |
| `policy_dependency_add` | добавление новой зависимости в проект |
| `policy_db_migrations` | создание и применение миграций БД |
| `policy_file_delete` | удаление файлов вне рамок текущей задачи |
| `policy_bypass_arch_lint` | ослабление/игнор проверки границ слоёв (правки `.importlinter`, `# noqa`-исключения импортов, пропуск `lint-imports`). `never` — протечку слоя чинят разворотом зависимости, а не заглушкой; ослабление контракта — только через ADR |
| `policy_external_api_calls` | реальные вызовы Bot API Telegram/MAX и любых внешних платформ (отправка сообщений живым ботам, регистрация webhook) |

Дополнительные флаги закрепляют строгий режим Clean Architecture
([../architecture/overview.md](../architecture/overview.md)) и защищают токены/боты
от случайных обращений к боевым платформам. Любой ключ с префиксом `policy_`
валидируется автоматически (MB081).

## Enforcement

- **Все агенты**: перед чувствительным действием сверяются с флагами;
  ссылка на политику стоит в AGENTS.md (раздел «Ограничения»).
- **Claude Code**: `policy_push` и `policy_pr_create` продублированы жёстко
  в `.claude/settings.json` (`permissions.deny`) — это техническая блокировка,
  а не просьба. Ослабляете политику — правьте оба места.
- **Валидатор**: значения всех `policy_*` флагов проверяются в CI.

## Как изменить

Только через PR с апрувом владельца `_meta/` ([governance.md](governance.md)).
При ослаблении (`never` → `ask`/`always`) — причина фиксируется в описании PR.
