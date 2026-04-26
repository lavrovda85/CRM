"""Equipment and depreciation management API endpoints.

CRUD операции над оборудованием, просмотр записей
амортизации и списание оборудования.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import PaginationParams, get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse
from app.models import DepreciationRecord, Equipment
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentDetailResponse,
    EquipmentResponse,
    EquipmentUpdate,
    EquipmentWriteOff,
)

router = APIRouter(prefix="/equipment")


def _raise_equipment_integrity_error(exc: IntegrityError) -> None:
    """Map DB integrity violations to a validation error; re-raise unknown causes."""
    orig = getattr(exc, "orig", None)
    det = " ".join(p for p in (str(exc), str(orig) if orig else "") if p)
    low = det.lower()
    if "uq_equipment_company_serial" in det or "company_serial" in low:
        raise ValidationError("serial_number", "This serial number already exists for the company") from exc
    if "equipment_assigned_to_fkey" in det or ("assigned_to" in low and "foreign key" in low):
        raise ValidationError("assigned_to", "Invalid user id for assigned_to") from exc
    raise ValidationError("equipment", "Could not save equipment (database constraint conflict)") from exc


@router.post("", response_model=EquipmentResponse, status_code=201)
async def register_equipment(
    body: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> EquipmentResponse:
    """Register new equipment.

    Регистрирует новое оборудование в системе.
    Начальная current_value равна purchase_price.

    Аргументы:
        body: Данные оборудования.
        db: Асинхронная сессия БД.
        ctx: Активная компания (тенант).

    Возвращает:
        Зарегистрированное оборудование.
    """
    equipment = Equipment(
        company_id=ctx.company_id,
        name=body.name,
        serial_number=body.serial_number,
        category=body.category,
        purchase_price=body.purchase_price,
        purchase_date=body.purchase_date,
        service_life_months=body.service_life_months,
        current_value=body.purchase_price,
        status="active",
        hourly_rate=body.hourly_rate,
        assigned_to=body.assigned_to,
        location=body.location,
        notes=body.notes,
    )
    db.add(equipment)
    try:
        await db.flush()
    except IntegrityError as exc:
        _raise_equipment_integrity_error(exc)
    except ProgrammingError as exc:
        raise ValidationError(
            "equipment",
            "Database schema mismatch (e.g. missing equipment columns). "
            "Set SCHEMA_BOOTSTRAP_ON_STARTUP=true and restart the API, or run migrations.",
        ) from exc
    await db.refresh(equipment)
    return EquipmentResponse.model_validate(equipment)


@router.get("", response_model=PaginatedResponse[EquipmentResponse])
async def list_equipment(
    status: str | None = Query(default=None, description="Filter by status"),
    category: str | None = Query(default=None, description="Filter by category"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assigned user"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
        ctx: Активная компания (тенант).

    Возвращает:
        Постраничный ответ со списком оборудования.
    """
    query = select(Equipment).where(Equipment.company_id == ctx.company_id)
    count_query = select(func.count(Equipment.id)).where(Equipment.company_id == ctx.company_id)

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
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> EquipmentDetailResponse:
    """Get equipment detail with depreciation records.

    Возвращает полную информацию об оборудовании,
    включая историю начислений амортизации.

    Аргументы:
        equipment_id: UUID оборудования.
        db: Асинхронная сессия БД.
        ctx: Активная компания (тенант).

    Возвращает:
        Детальную информацию об оборудовании.
    """
    result = await db.execute(
        select(Equipment)
        .options(selectinload(Equipment.depreciation_records))
        .where(Equipment.id == equipment_id, Equipment.company_id == ctx.company_id)
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
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> EquipmentResponse:
    """Update equipment fields.

    Частичное обновление данных оборудования.

    Аргументы:
        equipment_id: UUID оборудования.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        ctx: Активная компания (тенант).

    Возвращает:
        Обновлённое оборудование.
    """
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id, Equipment.company_id == ctx.company_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment", str(equipment_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        try:
            await db.execute(
                update(Equipment)
                .where(Equipment.id == equipment_id, Equipment.company_id == ctx.company_id)
                .values(**update_data)
            )
            await db.flush()
        except IntegrityError as exc:
            _raise_equipment_integrity_error(exc)
        except ProgrammingError as exc:
            raise ValidationError(
                "equipment",
                "Database schema mismatch (e.g. missing equipment columns). "
                "Set SCHEMA_BOOTSTRAP_ON_STARTUP=true and restart the API, or run migrations.",
            ) from exc
        await db.refresh(equipment)

    return EquipmentResponse.model_validate(equipment)


@router.post("/{equipment_id}/write-off", response_model=EquipmentResponse)
async def write_off_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentWriteOff,
    db: AsyncSession = Depends(get_db),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> EquipmentResponse:
    """Write off equipment.

    Списывает оборудование, устанавливая статус written_off
    и обнуляя остаточную стоимость. Создаёт финальную
    запись амортизации.

    Аргументы:
        equipment_id: UUID оборудования.
        body: Данные списания (причина).
        db: Асинхронная сессия БД.
        ctx: Активная компания (тенант).

    Возвращает:
        Оборудование с обновлённым статусом.
    """
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id, Equipment.company_id == ctx.company_id)
    )
    equipment = result.scalar_one_or_none()
    if not equipment:
        raise NotFoundError("Equipment", str(equipment_id))

    if equipment.status == "written_off":
        raise ValidationError("status", "Equipment is already written off")

    remaining = equipment.current_value
    accumulated_result = await db.execute(
        select(func.sum(DepreciationRecord.amount))
        .where(
            DepreciationRecord.equipment_id == equipment_id,
            DepreciationRecord.company_id == ctx.company_id,
        )
    )
    accumulated = accumulated_result.scalar() or 0

    if remaining > 0:
        db.add(DepreciationRecord(
            company_id=ctx.company_id,
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
        .where(Equipment.id == equipment_id, Equipment.company_id == ctx.company_id)
        .values(status="written_off", current_value=0)
    )
    await db.flush()
    await db.refresh(equipment)
    return EquipmentResponse.model_validate(equipment)
