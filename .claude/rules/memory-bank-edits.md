---
paths:
  - "memory-bank/**/*.md"
---

# Правила при редактировании базы знаний

Ты сейчас правишь файлы memory-bank. Обязательно:

1. `version`/`updated` не проставляй вручную — это делает автоматика
   (pre-commit и CI, `scripts/bump_frontmatter.py`); правила:
   `memory-bank/_meta/frontmatter.md`. Записи в `current/` — через
   `python scripts/mb_log.py`, он обновляет frontmatter сам.
2. Проверь, не является ли правимый факт производным: если у документа есть
   `derived_from` — сначала поправь канонический источник, потом этот документ.
3. Добавил/удалил/переименовал файл → обнови индекс `memory-bank/README.md`.
4. Противоречие с другим документом — не исправляй молча: зафиксируй в
   `memory-bank/current/progress.md` (раздел «Расхождения») и сообщи пользователю
   (протокол: `memory-bank/_meta/lifecycle.md`).
5. После правок прогони: `python scripts/validate_memory_bank.py`.
6. ADR со статусом `accepted` задним числом не редактируется по существу —
   создай новый ADR и пометь старый `superseded`
   (жизненный цикл ADR: `memory-bank/decisions/README.md`).
