"""Presentation-слой meta-bot-core: FastAPI-роуты, схемы, middleware.

Тонкий слой: транслирует HTTP <-> DTO и вызывает use cases application;
бизнес-логики и доступа к БД/адаптерам в обход application здесь нет
(memory-bank/architecture/overview.md).
"""
