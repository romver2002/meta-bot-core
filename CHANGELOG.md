# Changelog — meta-bot-core

Изменения проекта. Документы базы знаний версионируются отдельно, во frontmatter.

## 2026-07-06 — bootstrap

- Проект развёрнут из внутреннего шаблона memory bank; база знаний адаптирована под
  meta-bot-core — конструктор сценариев чат-ботов и mini app для Telegram и MAX.
- Заложен строгий режим Clean Architecture: контракт границ слоёв `.importlinter`
  (`lint-imports`), CI-джоба `arch-lint`, path-scoped правило
  `.claude/rules/clean-architecture.md`, политика `policy_bypass_arch_lint: never`.
- ADR: 0001 (Clean Architecture + SOLID, строгий режим, accepted), 0002 (доменное
  ядро + платформенные адаптеры, accepted), 0003–0006 (движок на блоках + песочница,
  webhook, capability matrix, mini app как web-продукт — proposed, ждут ратификации).
- Наполнены разделы product/domain/architecture/ops/workflows/current; добавлен
  проверенный справочник платформ `architecture/platform-reference.md` (Telegram
  Bot API и MAX Bot API, сверено с документацией 2026-07-06).
