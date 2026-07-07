"""Infrastructure-слой meta-bot-core: реализации портов application/domain.

Платформенные адаптеры (platforms/), БД (db/), песочница (code_executor/),
token vault. Бизнес-логики здесь нет; склейка со слоями — только в
composition root (src/main.py).
"""
