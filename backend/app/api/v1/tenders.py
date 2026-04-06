"""Tender management API endpoints.

CRUD операции над тендерами, привязка задач к тендерам.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Task, Tender
from app.schemas.task import TaskResponse
from app.schemas.tender import TenderCreate, TenderResponse, TenderUpdate

router = APIRouter(prefix="/tenders")


class TenderDetailResponse(TenderResponse):
    """Extended tender response with linked tasks.

    Атрибуты:
        tasks (list[TaskResponse]): Привязанные задачи.
    """

    tasks: list[TaskResponse] = Field(default_factory=list)


class LinkTasksRequest(BaseModel):
    """Schema for linking tasks to a tender.

    Атрибуты:
        task_ids (list[uuid.UUID]): Список ID задач для привязки.
    """

    task_ids: list[uuid.UUID]


@router.post("/", response_model=TenderResponse, status_code=201)
async def create_tender(
    body: TenderCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderResponse:
    """Create a new tender.

    Создаёт новый тендер с указанным статусом и бюджетом.

    Аргументы:
        body: Данные для создания тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный тендер.
    """
    tender = Tender(
        title=body.title,
        source=body.source,
        budget=body.budget,
        our_price=body.our_price,
        status=body.status,
        deadline=body.deadline,
        assigned_to=body.assigned_to,
        requirements=body.requirements,
        notes=body.notes,
    )
    db.add(tender)
    await db.flush()
    await db.refresh(tender)
    return TenderResponse.model_validate(tender)


@router.get("/", response_model=PaginatedResponse[TenderResponse])
async def list_tenders(
    status: str | None = Query(default=None, description="Filter by status"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assignee"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[TenderResponse]:
    """List tenders with optional filters.

    Возвращает постраничный список тендеров с фильтрацией
    по статусу и ответственному менеджеру.

    Аргументы:
        status: Фильтр по статусу тендера.
        assigned_to: Фильтр по ID ответственного.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком тендеров.
    """
    query = select(Tender)
    count_query = select(func.count(Tender.id))

    if status:
        query = query.where(Tender.status == status)
        count_query = count_query.where(Tender.status == status)
    if assigned_to:
        query = query.where(Tender.assigned_to == assigned_to)
        count_query = count_query.where(Tender.assigned_to == assigned_to)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Tender.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    tenders = result.scalars().all()

    return PaginatedResponse(
        items=[TenderResponse.model_validate(t) for t in tenders],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{tender_id}", response_model=TenderDetailResponse)
async def get_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderDetailResponse:
    """Get tender detail with linked tasks.

    Возвращает полную информацию о тендере,
    включая все привязанные задачи.

    Аргументы:
        tender_id: UUID тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о тендере.
    """
    result = await db.execute(
        select(Tender)
        .options(selectinload(Tender.tasks))
        .where(Tender.id == tender_id)
    )
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    tender_data = TenderResponse.model_validate(tender).model_dump()
    tender_data["tasks"] = [TaskResponse.model_validate(t) for t in tender.tasks]
    return TenderDetailResponse(**tender_data)


@router.patch("/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: uuid.UUID,
    body: TenderUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderResponse:
    """Update tender fields.

    Частичное обновление полей тендера.

    Аргументы:
        tender_id: UUID тендера.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый тендер.
    """
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Tender).where(Tender.id == tender_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(tender)

    return TenderResponse.model_validate(tender)


@router.post("/{tender_id}/link-tasks", response_model=TenderDetailResponse)
async def link_tasks_to_tender(
    tender_id: uuid.UUID,
    body: LinkTasksRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderDetailResponse:
    """Link tasks to a tender.

    Привязывает список задач к тендеру, устанавливая
    tender_id в каждой указанной задаче.

    Аргументы:
        tender_id: UUID тендера.
        body: Список ID задач для привязки.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый тендер с задачами.
    """
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    if body.task_ids:
        await db.execute(
            update(Task)
            .where(Task.id.in_(body.task_ids))
            .values(tender_id=tender_id)
        )
        await db.flush()

    return await get_tender(tender_id, db, user)


@router.delete("/{tender_id}", status_code=204)
async def delete_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a tender.

    Удаляет тендер. Привязанные задачи не удаляются —
    обнуляется их tender_id.

    Аргументы:
        tender_id: UUID тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    await db.execute(
        update(Task).where(Task.tender_id == tender_id).values(tender_id=None)
    )
    await db.delete(tender)
    await db.flush()
