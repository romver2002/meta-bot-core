"""Провайдеры Admin API (привязка — в composition root, src/main.py)."""

from __future__ import annotations

from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase


def get_create_bot_uc() -> CreateBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_get_bot_uc() -> GetBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_save_flow_draft_uc() -> SaveFlowDraftUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_publish_bot_uc() -> PublishBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")
