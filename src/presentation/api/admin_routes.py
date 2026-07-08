"""Admin API конструктора: создание бота, черновик сценария, публикация.

Тонкий слой: HTTP <-> DTO <-> use case. Аутентификация Admin API — открытый
вопрос (IAM), контур пока для доверенной среды разработки.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from application.errors import (
    BotCreationError,
    BotNotFoundError,
    ConcurrencyError,
    FlowNotFoundError,
)
from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from domain.bot.value_objects import Platform
from domain.errors import BotPublicationError, FlowIntegrityError, FlowValidationError
from presentation.providers.admin import (
    get_create_bot_uc,
    get_get_bot_uc,
    get_publish_bot_uc,
    get_save_flow_draft_uc,
)
from presentation.schemas.admin import (
    BotResponse,
    CreateBotRequest,
    PublishResponse,
    SaveFlowRequest,
    SaveFlowResponse,
)

admin = APIRouter()


@admin.post("/bots", status_code=status.HTTP_201_CREATED, summary="Создать бота по токену")
async def create_bot(
    request: CreateBotRequest,
    use_case: Annotated[CreateBotUseCase, Depends(get_create_bot_uc)],
) -> BotResponse:
    try:
        bot = await use_case.execute(
            name=request.name,
            platform=Platform(request.platform),
            token_secret=request.token,
        )
    except BotCreationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return BotResponse.from_domain(bot)


@admin.get("/bots/{bot_id}", summary="Карточка бота")
async def get_bot(
    bot_id: str,
    use_case: Annotated[GetBotUseCase, Depends(get_get_bot_uc)],
) -> BotResponse:
    try:
        bot = await use_case.execute(bot_id)
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BotResponse.from_domain(bot)


@admin.put("/bots/{bot_id}/flow", summary="Сохранить черновик сценария (из редактора)")
async def save_flow_draft(
    bot_id: str,
    request: SaveFlowRequest,
    use_case: Annotated[SaveFlowDraftUseCase, Depends(get_save_flow_draft_uc)],
) -> SaveFlowResponse:
    try:
        saved = await use_case.execute(
            bot_id,
            request.definition,
            expected_row_version=request.row_version,
            name=request.name,
        )
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConcurrencyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FlowIntegrityError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SaveFlowResponse(flow_id=saved.flow_id, row_version=saved.row_version)


@admin.post("/bots/{bot_id}/publish", summary="Опубликовать бота (BR-001 + BR-006)")
async def publish_bot(
    bot_id: str,
    use_case: Annotated[PublishBotUseCase, Depends(get_publish_bot_uc)],
) -> PublishResponse:
    try:
        bot = await use_case.execute(bot_id)
    except (BotNotFoundError, FlowNotFoundError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConcurrencyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (FlowValidationError, BotPublicationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return PublishResponse(bot=BotResponse.from_domain(bot))
