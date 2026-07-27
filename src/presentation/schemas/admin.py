"""Схемы Admin API конструктора."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from domain.bot.entities import Bot


class CreateBotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: Literal["telegram", "max"]
    token: str = Field(min_length=1, description="Токен уже зарегистрированного бота (BR-002)")


class MiniAppInfo(BaseModel):
    """Привязанная mini app бота (BR-003): редактору нужно знать факт привязки."""

    url: str
    title: str


class BotResponse(BaseModel):
    """Токен наружу не возвращается никогда — только факт его наличия в vault."""

    id: str
    name: str
    platform: str
    status: str
    flow_id: str | None
    published_flow_version_id: str | None
    mini_app: MiniAppInfo | None

    @classmethod
    def from_domain(cls, bot: Bot) -> BotResponse:
        return cls(
            id=bot.id,
            name=bot.name,
            platform=bot.platform.value,
            status=bot.status.value,
            flow_id=bot.flow_id,
            published_flow_version_id=bot.published_flow_version_id,
            mini_app=(
                MiniAppInfo(url=bot.mini_app.url, title=bot.mini_app.title)
                if bot.mini_app is not None
                else None
            ),
        )


class BotListResponse(BaseModel):
    """Реестр ботов конструктора («Мои боты»), новые первыми; токенов нет."""

    bots: list[BotResponse]


class SaveFlowRequest(BaseModel):
    definition: dict[str, Any] = Field(description="Контракт domain/flow/codec.py (редактор)")
    row_version: int | None = Field(
        default=None,
        description="Токен конкуренции из прошлого ответа; None — создать новый черновик",
    )
    name: str = ""


class SaveFlowResponse(BaseModel):
    flow_id: str
    row_version: int


class FlowDraftResponse(BaseModel):
    """Read-контракт черновика: definition + row_version для безопасного save."""

    flow_id: str
    name: str
    definition: dict[str, Any] = Field(description="Канонический контракт domain/flow/codec.py")
    row_version: int


class PublishResponse(BaseModel):
    bot: BotResponse


class MiniAppAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, description="Сырое window.*.WebApp.initData (BR-007)")


class MiniAppAuthResponse(BaseModel):
    external_user_id: str


class AttachMiniAppRequest(BaseModel):
    url: str = Field(min_length=1, description="HTTPS-URL mini app (BR-003)")
    title: str = ""


class MiniAppResultRequest(BaseModel):
    init_data: str = Field(min_length=1)
    result: dict[str, Any] = Field(default_factory=dict)


class SetConnectionSecretRequest(BaseModel):
    value: str = Field(min_length=1, description="Секрет интеграции (ключ внешнего API)")


class SetNotificationTargetRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=128, description="external_chat_id адресата роли (ADR-0010)")


class SetEventsTokenRequest(BaseModel):
    token: str = Field(
        min_length=16,
        max_length=256,
        description="Bot-scoped токен входа внешних событий (ADR-0017); хранится отдельно от секретов подключений",
    )


class EventTargetRequest(BaseModel):
    """Адресат события: ровно одно из role / chat_id (v1 — только личные чаты)."""

    role: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    chat_id: str | None = Field(default=None, min_length=1, max_length=128)


class SubmitEventRequest(BaseModel):
    event: str = Field(min_length=1, max_length=64, description="Имя события — матчится с config[event] триггера external_event")
    to: EventTargetRequest
    payload: dict[str, str] = Field(default_factory=dict, description="Плоский словарь → переменные сессии (BR-010)")
    event_id: str | None = Field(default=None, min_length=1, max_length=128, description="Ключ идемпотентности ретраев вызывающего")


class EventAck(BaseModel):
    delivered: bool = Field(description="False — дубль по event_id, событие уже доставлялось")
