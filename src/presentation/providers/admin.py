"""Провайдеры Admin API (привязка — в composition root, src/main.py)."""

from __future__ import annotations

from application.use_cases.attach_mini_app import AttachMiniAppUseCase
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.get_flow_draft import GetFlowDraftUseCase
from application.use_cases.list_bots import ListBotsUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from application.use_cases.set_connection_secret import SetConnectionSecretUseCase
from application.use_cases.set_notification_target import SetNotificationTargetUseCase
from application.use_cases.submit_mini_app_result import SubmitMiniAppResultUseCase


def get_create_bot_uc() -> CreateBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_authenticate_mini_app_uc() -> AuthenticateMiniAppUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_attach_mini_app_uc() -> AttachMiniAppUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_submit_mini_app_result_uc() -> SubmitMiniAppResultUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_set_connection_secret_uc() -> SetConnectionSecretUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_set_notification_target_uc() -> SetNotificationTargetUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_get_bot_uc() -> GetBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_list_bots_uc() -> ListBotsUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_save_flow_draft_uc() -> SaveFlowDraftUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_get_flow_draft_uc() -> GetFlowDraftUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")


def get_publish_bot_uc() -> PublishBotUseCase:
    raise NotImplementedError("Провайдер подключается в composition root (src/main.py)")
