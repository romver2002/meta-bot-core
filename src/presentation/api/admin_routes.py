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
    MiniAppAuthError,
)
from application.use_cases.attach_mini_app import AttachMiniAppUseCase
from application.use_cases.authenticate_mini_app import AuthenticateMiniAppUseCase
from application.use_cases.create_bot import CreateBotUseCase
from application.use_cases.get_bot import GetBotUseCase
from application.use_cases.publish_bot import PublishBotUseCase
from application.use_cases.save_flow_draft import SaveFlowDraftUseCase
from application.use_cases.set_connection_secret import SetConnectionSecretUseCase
from application.use_cases.submit_mini_app_result import SubmitMiniAppResultUseCase
from domain.bot.value_objects import Platform
from domain.errors import (
    BotPublicationError,
    FlowIntegrityError,
    FlowValidationError,
    MiniAppInvariantError,
)
from presentation.providers.admin import (
    get_attach_mini_app_uc,
    get_authenticate_mini_app_uc,
    get_create_bot_uc,
    get_get_bot_uc,
    get_publish_bot_uc,
    get_save_flow_draft_uc,
    get_set_connection_secret_uc,
    get_submit_mini_app_result_uc,
)
from presentation.schemas.admin import (
    AttachMiniAppRequest,
    BotResponse,
    CreateBotRequest,
    MiniAppAuthRequest,
    MiniAppAuthResponse,
    MiniAppResultRequest,
    PublishResponse,
    SaveFlowRequest,
    SaveFlowResponse,
    SetConnectionSecretRequest,
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


@admin.post("/bots/{bot_id}/miniapp/auth", summary="Валидация init data mini app (BR-007)")
async def authenticate_mini_app(
    bot_id: str,
    request: MiniAppAuthRequest,
    use_case: Annotated[AuthenticateMiniAppUseCase, Depends(get_authenticate_mini_app_uc)],
) -> MiniAppAuthResponse:
    try:
        identity = await use_case.execute(bot_id, request.init_data)
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MiniAppAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return MiniAppAuthResponse(external_user_id=identity.external_user_id)


@admin.put("/bots/{bot_id}/miniapp", summary="Привязать mini app к боту (BR-003)")
async def attach_mini_app(
    bot_id: str,
    request: AttachMiniAppRequest,
    use_case: Annotated[AttachMiniAppUseCase, Depends(get_attach_mini_app_uc)],
) -> BotResponse:
    try:
        bot = await use_case.execute(bot_id, request.url, title=request.title)
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MiniAppInvariantError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return BotResponse.from_domain(bot)


@admin.post("/bots/{bot_id}/miniapp/result", summary="Результат mini app -> сценарий (mini_app_result)")
async def submit_mini_app_result(
    bot_id: str,
    request: MiniAppResultRequest,
    use_case: Annotated[SubmitMiniAppResultUseCase, Depends(get_submit_mini_app_result_uc)],
) -> dict[str, bool]:
    try:
        await use_case.execute(bot_id, request.init_data, request.result)
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except MiniAppAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {"ok": True}


@admin.put(
    "/bots/{bot_id}/connections/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Задать секрет подключения (ключ внешнего API для http_request)",
)
async def set_connection_secret(
    bot_id: str,
    name: str,
    request: SetConnectionSecretRequest,
    use_case: Annotated[SetConnectionSecretUseCase, Depends(get_set_connection_secret_uc)],
) -> None:
    try:
        await use_case.execute(bot_id, name, request.value)
    except BotNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
