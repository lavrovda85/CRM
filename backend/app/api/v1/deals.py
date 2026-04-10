"""Deal and pipeline stage management API endpoints.

CRUD операции над сделками и стадиями воронки продаж.
Перемещение сделок между стадиями.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Deal, DealStage
from app.schemas.deal import (
    DealCreate,
    DealResponse,
    DealStageCreate,
    DealStageResponse,
    DealUpdate,
)

router = APIRouter(prefix="/deals")


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    body: DealCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DealResponse:
    """Create a new deal in the pipeline.

    Создаёт новую сделку, привязанную к клиенту
    и определённой стадии воронки продаж.

    Аргументы:
        body: Данные для создания сделки.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную сделку.
    """
    stage_result = await db.execute(
        select(DealStage).where(DealStage.id == body.stage_id)
    )
    if not stage_result.scalar_one_or_none():
        raise NotFoundError("DealStage", str(body.stage_id))

    deal = Deal(
        client_id=body.client_id,
        title=body.title,
        amount=body.amount,
        stage_id=body.stage_id,
        assigned_to=body.assigned_to,
        expected_close=body.expected_close,
        source=body.source,
    )
    db.add(deal)
    await db.flush()
    await db.refresh(deal)
    return DealResponse.model_validate(deal)


@router.get("", response_model=PaginatedResponse[DealResponse])
async def list_deals(
    stage_id: uuid.UUID | None = Query(default=None, description="Filter by stage"),
    client_id: uuid.UUID | None = Query(default=None, description="Filter by client"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assignee"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[DealResponse]:
    """List deals with optional filters.

    Возвращает постраничный список сделок с фильтрацией
    по стадии, клиенту и ответственному менеджеру.

    Аргументы:
        stage_id: Фильтр по ID стадии воронки.
        client_id: Фильтр по ID клиента.
        assigned_to: Фильтр по ID ответственного.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком сделок.
    """
    query = select(Deal)
    count_query = select(func.count(Deal.id))

    if stage_id:
        query = query.where(Deal.stage_id == stage_id)
        count_query = count_query.where(Deal.stage_id == stage_id)
    if client_id:
        query = query.where(Deal.client_id == client_id)
        count_query = count_query.where(Deal.client_id == client_id)
    if assigned_to:
        query = query.where(Deal.assigned_to == assigned_to)
        count_query = count_query.where(Deal.assigned_to == assigned_to)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Deal.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    deals = result.scalars().all()

    return PaginatedResponse(
        items=[DealResponse.model_validate(d) for d in deals],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/stages", response_model=list[DealStageResponse])
async def list_stages(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[DealStageResponse]:
    """List all pipeline stages ordered by position.

    Возвращает все стадии воронки продаж,
    отсортированные по порядковому номеру.

    Аргументы:
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Список стадий воронки.
    """
    result = await db.execute(select(DealStage).order_by(DealStage.order))
    return [DealStageResponse.model_validate(s) for s in result.scalars().all()]


@router.post("/stages", response_model=DealStageResponse, status_code=201)
async def create_stage(
    body: DealStageCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DealStageResponse:
    """Create a new pipeline stage.

    Создаёт новую стадию воронки продаж.

    Аргументы:
        body: Данные стадии.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную стадию.
    """
    stage = DealStage(
        name=body.name,
        order=body.order,
        color=body.color,
        is_won=body.is_won,
        is_lost=body.is_lost,
    )
    db.add(stage)
    await db.flush()
    await db.refresh(stage)
    return DealStageResponse.model_validate(stage)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DealResponse:
    """Get deal detail.

    Возвращает полную информацию о сделке.

    Аргументы:
        deal_id: UUID сделки.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о сделке.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise NotFoundError("Deal", str(deal_id))
    return DealResponse.model_validate(deal)


@router.patch("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    body: DealUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DealResponse:
    """Update deal fields or move to another stage.

    Частичное обновление полей сделки, включая
    перемещение между стадиями воронки.

    Аргументы:
        deal_id: UUID сделки.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую сделку.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise NotFoundError("Deal", str(deal_id))

    update_data = body.model_dump(exclude_unset=True)
    if "stage_id" in update_data and update_data["stage_id"]:
        stage_check = await db.execute(
            select(DealStage).where(DealStage.id == update_data["stage_id"])
        )
        if not stage_check.scalar_one_or_none():
            raise NotFoundError("DealStage", str(update_data["stage_id"]))

    if update_data:
        await db.execute(
            update(Deal).where(Deal.id == deal_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(deal)

    return DealResponse.model_validate(deal)


@router.delete("/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a deal.

    Удаляет сделку из системы.

    Аргументы:
        deal_id: UUID сделки.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise NotFoundError("Deal", str(deal_id))
    await db.delete(deal)
    await db.flush()
