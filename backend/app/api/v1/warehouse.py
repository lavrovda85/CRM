"""Warehouse management API endpoints.

CRUD операции над складскими позициями, движениями
(приход/расход/списание) и резервированием.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError, WarehouseInsufficientStockError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import User, WarehouseItem, WarehouseMovement, WarehouseReservation
from app.schemas.warehouse import (
    ReservationCreate,
    ReservationResponse,
    WarehouseItemCreate,
    WarehouseItemResponse,
    WarehouseItemUpdate,
    WarehouseMovementCreate,
    WarehouseMovementResponse,
)

router = APIRouter(prefix="/warehouse")

CONSUMPTION_TYPES = {"consumption", "write_off", "transfer"}
INTAKE_TYPES = {"intake", "return"}


@router.post("/items", response_model=WarehouseItemResponse, status_code=201)
async def create_item(
    body: WarehouseItemCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseItemResponse:
    """Create a warehouse item.

    Создаёт новую складскую позицию.

    Аргументы:
        body: Данные складской позиции.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную складскую позицию.
    """
    item = WarehouseItem(
        name=body.name,
        sku=body.sku,
        category=body.category,
        unit=body.unit,
        quantity=body.quantity,
        min_quantity=body.min_quantity,
        price=body.price,
        description=body.description,
        location=body.location,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return WarehouseItemResponse.model_validate(item)


@router.get("/items", response_model=PaginatedResponse[WarehouseItemResponse])
async def list_items(
    category: str | None = Query(default=None, description="Filter by category"),
    low_stock: bool = Query(default=False, description="Show only low stock items"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[WarehouseItemResponse]:
    """List warehouse items with optional filters.

    Возвращает постраничный список складских позиций
    с фильтрацией по категории и признаку низкого остатка.

    Аргументы:
        category: Фильтр по категории.
        low_stock: Показать только позиции с остатком ниже минимума.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком позиций.
    """
    query = select(WarehouseItem)
    count_query = select(func.count(WarehouseItem.id))

    if category:
        query = query.where(WarehouseItem.category == category)
        count_query = count_query.where(WarehouseItem.category == category)
    if low_stock:
        query = query.where(WarehouseItem.quantity <= WarehouseItem.min_quantity)
        count_query = count_query.where(WarehouseItem.quantity <= WarehouseItem.min_quantity)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(WarehouseItem.name)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    items = result.scalars().all()

    return PaginatedResponse(
        items=[WarehouseItemResponse.model_validate(i) for i in items],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/items/{item_id}", response_model=WarehouseItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseItemResponse:
    """Get warehouse item detail with recent movements.

    Возвращает информацию о складской позиции.

    Аргументы:
        item_id: UUID позиции.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о позиции.
    """
    result = await db.execute(
        select(WarehouseItem).where(WarehouseItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(item_id))
    return WarehouseItemResponse.model_validate(item)


@router.patch("/items/{item_id}", response_model=WarehouseItemResponse)
async def update_item(
    item_id: uuid.UUID,
    body: WarehouseItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseItemResponse:
    """Update warehouse item fields.

    Частичное обновление данных складской позиции.

    Аргументы:
        item_id: UUID позиции.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую позицию.
    """
    result = await db.execute(
        select(WarehouseItem).where(WarehouseItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(item_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(WarehouseItem)
            .where(WarehouseItem.id == item_id)
            .values(**update_data)
        )
        await db.flush()
        await db.refresh(item)

    return WarehouseItemResponse.model_validate(item)


@router.post("/movements", response_model=WarehouseMovementResponse, status_code=201)
async def record_movement(
    body: WarehouseMovementCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseMovementResponse:
    """Record a warehouse movement (intake, consumption, write-off, transfer).

    Создаёт запись о движении материалов. Автоматически
    обновляет quantity складской позиции.

    Аргументы:
        body: Данные движения.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную запись движения.
    """
    item_result = await db.execute(
        select(WarehouseItem).where(WarehouseItem.id == body.item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(body.item_id))

    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    if body.movement_type in CONSUMPTION_TYPES:
        available = item.quantity - item.reserved_quantity
        if body.quantity > available:
            raise WarehouseInsufficientStockError(
                item_id=str(body.item_id),
                requested=float(body.quantity),
                available=float(available),
            )
        new_quantity = item.quantity - body.quantity
    elif body.movement_type in INTAKE_TYPES:
        new_quantity = item.quantity + body.quantity
    else:
        new_quantity = item.quantity

    await db.execute(
        update(WarehouseItem)
        .where(WarehouseItem.id == body.item_id)
        .values(quantity=new_quantity)
    )

    movement = WarehouseMovement(
        item_id=body.item_id,
        task_id=body.task_id,
        user_id=db_user.id,
        movement_type=body.movement_type,
        quantity=body.quantity,
        unit_price=item.price,
        reason=body.reason,
        destination=body.destination,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)
    return WarehouseMovementResponse.model_validate(movement)


@router.get("/movements", response_model=PaginatedResponse[WarehouseMovementResponse])
async def list_movements(
    item_id: uuid.UUID | None = Query(default=None, description="Filter by item"),
    movement_type: str | None = Query(default=None, description="Filter by type"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[WarehouseMovementResponse]:
    """List warehouse movements with optional filters.

    Возвращает постраничный список движений материалов
    с фильтрацией по позиции и типу движения.

    Аргументы:
        item_id: Фильтр по ID позиции.
        movement_type: Фильтр по типу движения.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком движений.
    """
    query = select(WarehouseMovement)
    count_query = select(func.count(WarehouseMovement.id))

    if item_id:
        query = query.where(WarehouseMovement.item_id == item_id)
        count_query = count_query.where(WarehouseMovement.item_id == item_id)
    if movement_type:
        query = query.where(WarehouseMovement.movement_type == movement_type)
        count_query = count_query.where(WarehouseMovement.movement_type == movement_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(WarehouseMovement.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    movements = result.scalars().all()

    return PaginatedResponse(
        items=[WarehouseMovementResponse.model_validate(m) for m in movements],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.post("/reservations", response_model=ReservationResponse, status_code=201)
async def create_reservation(
    body: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ReservationResponse:
    """Create a material reservation for a task.

    Резервирует материалы для задачи. Проверяет доступность
    (количество минус уже зарезервированное).

    Аргументы:
        body: Данные резервирования.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный резерв.
    """
    item_result = await db.execute(
        select(WarehouseItem).where(WarehouseItem.id == body.item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(body.item_id))

    available = item.quantity - item.reserved_quantity
    if body.quantity > available:
        raise WarehouseInsufficientStockError(
            item_id=str(body.item_id),
            requested=float(body.quantity),
            available=float(available),
        )

    await db.execute(
        update(WarehouseItem)
        .where(WarehouseItem.id == body.item_id)
        .values(reserved_quantity=item.reserved_quantity + body.quantity)
    )

    reservation = WarehouseReservation(
        item_id=body.item_id,
        task_id=body.task_id,
        quantity=body.quantity,
        status="reserved",
    )
    db.add(reservation)
    await db.flush()
    await db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)


@router.get("/reservations", response_model=PaginatedResponse[ReservationResponse])
async def list_reservations(
    item_id: uuid.UUID | None = Query(default=None, description="Filter by item"),
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task"),
    status: str | None = Query(default=None, description="Filter by reservation status"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[ReservationResponse]:
    """List warehouse reservations with optional filters.

    Возвращает постраничный список резервов
    с фильтрацией по позиции, задаче и статусу.

    Аргументы:
        item_id: Фильтр по ID позиции.
        task_id: Фильтр по ID задачи.
        status: Фильтр по статусу резерва.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком резервов.
    """
    query = select(WarehouseReservation)
    count_query = select(func.count(WarehouseReservation.id))

    if item_id:
        query = query.where(WarehouseReservation.item_id == item_id)
        count_query = count_query.where(WarehouseReservation.item_id == item_id)
    if task_id:
        query = query.where(WarehouseReservation.task_id == task_id)
        count_query = count_query.where(WarehouseReservation.task_id == task_id)
    if status:
        query = query.where(WarehouseReservation.status == status)
        count_query = count_query.where(WarehouseReservation.status == status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(WarehouseReservation.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    reservations = result.scalars().all()

    return PaginatedResponse(
        items=[ReservationResponse.model_validate(r) for r in reservations],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )
