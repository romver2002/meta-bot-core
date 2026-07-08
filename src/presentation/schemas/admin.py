"""Схемы Admin API конструктора."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from domain.bot.entities import Bot


class CreateBotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: Literal["telegram", "max"]
    token: str = Field(min_length=1, description="Токен уже зарегистрированного бота (BR-002)")


class BotResponse(BaseModel):
    """Токен наружу не возвращается никогда — только факт его наличия в vault."""

    id: str
    name: str
    platform: str
    status: str
    flow_id: str | None
    published_flow_version_id: str | None

    @classmethod
    def from_domain(cls, bot: Bot) -> BotResponse:
        return cls(
            id=bot.id,
            name=bot.name,
            platform=bot.platform.value,
            status=bot.status.value,
            flow_id=bot.flow_id,
            published_flow_version_id=bot.published_flow_version_id,
        )


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
