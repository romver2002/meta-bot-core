"""Провайдеры зависимостей роутов.

Отличие от sro-agent-core: наш контракт .importlinter запрещает presentation
импортировать infrastructure, поэтому провайдеры здесь — точки подключения,
а реальные фабрики привязывает composition root (src/main.py) через
FastAPI dependency_overrides.
"""
