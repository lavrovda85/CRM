"""Equipment and depreciation management API endpoints.

CRUD операции над оборудованием, просмотр записей
амортизации и списание оборудования.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import DepreciationRecord, Equipment
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentDetailResponse,
    EquipmentResponse,
    EquipmentUpdate,
    EquipmentWriteOff,
)

router = APIRouter(prefix="/equipment")


@router.post("", response_model=EquipmentResponse, status_code=201)
async def register_equipment(
    body: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EquipmentResponse:
    """Register new equipment.

    Регистрирует новое оборудование в системе.
    Начальная current_value равна purchase_price.

    Аргументы:
        body: Данные оборудования.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Зарегистрированное оборудование.
    """
    equipment = Equipment(
        name=body.name,
        serial_number=body.serial_number,
        category=body.category,
        purchase_price=body.purchase_price,
        purchase_date=body.purchase_date,
        service_life_months=body.service_life_months,
        current_value=body.purchase_price,
        status="active",
        assigned_to=body.assigned_to,
        location=body.location,
        notes=body.notes,
    )
    db.add(equipment)
    await db.flush()
    await db.refresh(equipment)
    return EquipmentResponse.model_validate(equipment)


@router.get("", response_model=PaginatedResponse[EquipmentResponse])
async def list_equipment(
    status: str | None = Query(default=None, description="Filter by status"),
    category: str | None = Query(default=None, description="Filter by category"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assigned user"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[EquipmentResponse]:
    """List equipment with optional filters.

    Возвращает постраничный список оборудования
    с фильтрацией по статусу, категории и закреплению.

    Аргументы:
        status: Фильтр по статусу — active, maintenance, written_off, lost.
        category: Фильтр по категории.
        assigned_to: Фильтр по ID закреплённого сотрудника.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком оборудования.
    """
    query = select(Equipment)
    count_query = select(func.count(Equipment.id))

    if status:
        query = query.where(Equipment.status == status)
        count_query = count_query.where(Equipment.status == status)
    if category:
        query = query.where(Equipment.category == category)
        count_query = count_query.where(Equipment.category == category)
    if assigned_to:
        query = query.where(Equipment.assigned_to == assigned_to)
        count_query = count_query.where(Equipment.assigned_to == assigned_to)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Equipment.name)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    items = result.scalars().all()

    return PaginatedResponse(
        items=[EquipmentResponse.model_validate(e) for e in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{equipment_id}", response_model=EquipmentDetailResponse)
async def get_equipment(
    equipment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EquipmentDetailResponse:
    """Get equipment detail with depreciation records.

    Возвращает полную информацию об оборудовании,
    включая историю начислений амортизации.

    Аргументы:
        equipment_id: UUID оборудования.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию об оборудовании.
    """
    result = await db.execute(
        select(Equipment)
        .options(selectinload(Equipment.depreciation_records))
        .where(Equipment.id == equipment_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment", str(equipment_id))
    return EquipmentDetailResponse.model_validate(equipment)


@router.patch("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EquipmentResponse:
    """Update equipment fields.

    Частичное обновление данных оборудования.

    Аргументы:
        equipment_id: UUID оборудования.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённое оборудование.
    """
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment", str(equipment_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Equipment)
            .where(Equipment.id == equipment_id)
            .values(**update_data)
        )
        await db.flush()
        await db.refresh(equipment)

    return EquipmentResponse.model_validate(equipment)


@router.post("/{equipment_id}/write-off", response_model=EquipmentResponse)
async def write_off_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentWriteOff,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> EquipmentResponse:
    """Write off equipment.

    Списывает оборудование, устанавливая статус written_off
    и обнуляя остаточную стоимость. Создаёт финальную
    запись амортизации.

    Аргументы:
        equipment_id: UUID оборудования.
        body: Данные списания (причина).
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Оборудование с обновлённым статусом.
    """
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment", str(equipment_id))

    if equipment.status == "written_off":
        raise ValidationError("status", "Equipment is already written off")

    remaining = equipment.current_value
    accumulated_result = await db.execute(
        select(func.sum(DepreciationRecord.amount))
        .where(DepreciationRecord.equipment_id == equipment_id)
    )
    accumulated = accumulated_result.scalar() or 0

    if remaining > 0:
        db.add(DepreciationRecord(
            equipment_id=equipment_id,
            period_date=datetime.now(timezone.utc).date(),
            amount=remaining,
            accumulated=accumulated + remaining,
            remaining_value=0,
            method="write_off",
            notes=body.reason,
        ))

    await db.execute(
        update(Equipment)
        .where(Equipment.id == equipment_id)
        .values(status="written_off", current_value=0)
    )
    await db.flush()
    await db.refresh(equipment)
    return EquipmentResponse.model_validate(equipment)
