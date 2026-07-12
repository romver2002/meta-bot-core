"""Infrastructure-слой meta-bot-core: реализации портов application/domain.

Платформенные адаптеры (platforms/), БД (db/), token vault (security/);
песочница code_executor/ запланирована (ADR-0003) и пока не реализована.
Бизнес-логики здесь нет; склейка со слоями — только в
composition root (src/main.py).
"""
