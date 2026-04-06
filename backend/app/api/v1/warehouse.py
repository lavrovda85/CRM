"""Warehouse management API endpoints.

CRUD операции над складскими позициями, движениями
(приход/расход/списание) и резервированием.
"""

import uuid
from io import BytesIO
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from fastapi import APIRouter, Depends, Query, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import User, WarehouseItem, WarehouseMovement, WarehouseReservation
from app.services import warehouse_operations
from app.schemas.warehouse import (
    ReservationCreate,
    ReservationResponse,
    WarehouseItemCreate,
    WarehouseItemResponse,
    WarehouseItemsImportResponse,
    WarehouseItemUpdate,
    WarehouseMovementCreate,
    WarehouseMovementResponse,
)

router = APIRouter(prefix="/warehouse")

# Simplified depreciation rules for warehouse items.
# - materials/consumables: not depreciable
# - tools/equipment: depreciable with default service life (months)
_DEPRECIABLE_CATEGORIES: dict[str, int] = {
    "tools": 36,
    "equipment": 60,
}


def _calc_financials(item: WarehouseItem) -> tuple[Decimal, Decimal, Decimal, float]:
    """Calculate cost and simplified depreciation for a warehouse item.

    Notes:
        This is an "accounting UI" approximation based on `created_at` as purchase date.
        A precise FIFO/LIFO model would require per-intake lot tracking.
    """

    quantity = Decimal(item.quantity or 0)
    price = Decimal(item.price or 0)
    cost_total = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    service_life_months = _DEPRECIABLE_CATEGORIES.get(item.category, 0)
    if cost_total <= 0 or service_life_months <= 0:
        return cost_total, Decimal("0.00"), cost_total, 0.0

    now = datetime.now(timezone.utc)
    created_at = item.created_at
    # Approximate months elapsed as days/30.
    months_elapsed = Decimal((now - created_at).days) / Decimal("30")
    if months_elapsed <= 0:
        return cost_total, Decimal("0.00"), cost_total, 0.0

    depr_fraction_raw = months_elapsed / Decimal(service_life_months)
    depr_fraction = min(max(depr_fraction_raw, Decimal("0")), Decimal("1"))
    depreciation_total = (cost_total * depr_fraction).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    remaining_value_total = (cost_total - depreciation_total).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    depreciation_pct = float((depr_fraction * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_DOWN))

    return cost_total, depreciation_total, remaining_value_total, depreciation_pct


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
    cost_total, depreciation_total, remaining_value_total, depreciation_pct = _calc_financials(item)
    return WarehouseItemResponse.model_validate(item).model_copy(
        update={
            "cost_total": cost_total,
            "depreciation_total": depreciation_total,
            "remaining_value_total": remaining_value_total,
            "depreciation_pct": depreciation_pct,
        }
    )


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
        items=[
            WarehouseItemResponse.model_validate(i).model_copy(
                update=dict(
                    zip(
                        ["cost_total", "depreciation_total", "remaining_value_total", "depreciation_pct"],
                        _calc_financials(i),
                    )
                )
            )
            for i in items
        ],
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
    cost_total, depreciation_total, remaining_value_total, depreciation_pct = _calc_financials(item)
    return WarehouseItemResponse.model_validate(item).model_copy(
        update={
            "cost_total": cost_total,
            "depreciation_total": depreciation_total,
            "remaining_value_total": remaining_value_total,
            "depreciation_pct": depreciation_pct,
        }
    )


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

    cost_total, depreciation_total, remaining_value_total, depreciation_pct = _calc_financials(item)
    return WarehouseItemResponse.model_validate(item).model_copy(
        update={
            "cost_total": cost_total,
            "depreciation_total": depreciation_total,
            "remaining_value_total": remaining_value_total,
            "depreciation_pct": depreciation_pct,
        }
    )


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
    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    movement, _new_qty = await warehouse_operations.record_movement(
        db,
        item_id=body.item_id,
        movement_type=body.movement_type,
        quantity=body.quantity,
        user_id=db_user.id,
        task_id=body.task_id,
        reason=body.reason,
        destination=body.destination,
    )
    return WarehouseMovementResponse.model_validate(movement)


@router.get("/movements", response_model=PaginatedResponse[WarehouseMovementResponse])
async def list_movements(
    item_id: uuid.UUID | None = Query(default=None, description="Filter by item"),
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task"),
    movement_type: str | None = Query(default=None, description="Filter by type"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[WarehouseMovementResponse]:
    """List warehouse movements with optional filters.

    Возвращает постраничный список движений материалов
    с фильтрацией по позиции, задаче и типу движения.

    Аргументы:
        item_id: Фильтр по ID позиции.
        task_id: Фильтр по ID задачи.
        movement_type: Фильтр по типу движения.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком движений.
    """
    from sqlalchemy.orm import selectinload

    query = select(WarehouseMovement).options(selectinload(WarehouseMovement.item))
    count_query = select(func.count(WarehouseMovement.id))

    if item_id:
        query = query.where(WarehouseMovement.item_id == item_id)
        count_query = count_query.where(WarehouseMovement.item_id == item_id)
    if task_id:
        query = query.where(WarehouseMovement.task_id == task_id)
        count_query = count_query.where(WarehouseMovement.task_id == task_id)
    if movement_type:
        query = query.where(WarehouseMovement.movement_type == movement_type)
        count_query = count_query.where(WarehouseMovement.movement_type == movement_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(WarehouseMovement.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    movements = result.unique().scalars().all()

    def to_response(m: WarehouseMovement) -> WarehouseMovementResponse:
        data = WarehouseMovementResponse.model_validate(m).model_dump()
        data["item_name"] = m.item.name if m.item else None
        return WarehouseMovementResponse(**data)

    return PaginatedResponse(
        items=[to_response(m) for m in movements],
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
    reservation = await warehouse_operations.create_reservation(
        db,
        item_id=body.item_id,
        task_id=body.task_id,
        quantity=body.quantity,
    )
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


@router.get("/items/export")
async def export_warehouse_items(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=5000, ge=1, le=20000, description="Max rows to export"),
) -> StreamingResponse:
    """Export warehouse items to an Excel (XLSX) file."""

    # Late import to keep base runtime light.
    from openpyxl import Workbook

    result = await db.execute(select(WarehouseItem).order_by(WarehouseItem.name).limit(limit))
    items = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "warehouse_items"

    headers = [
        "Название",
        "Артикул (SKU)",
        "Категория",
        "Ед. изм.",
        "Количество",
        "Мин. остаток",
        "Цена за ед.",
        "Место хранения",
        "Описание",
        "Дата создания",
    ]
    ws.append(headers)

    for i in items:
        ws.append(
            [
                i.name,
                i.sku,
                i.category,
                i.unit,
                float(i.quantity),
                float(i.min_quantity),
                float(i.price),
                i.location,
                i.description,
                i.created_at.isoformat(),
            ]
        )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = "warehouse_items.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/items/import", response_model=WarehouseItemsImportResponse)
async def import_warehouse_items(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseItemsImportResponse:
    """Import warehouse items from an Excel/XLSX export (including 1C exports).

    Supported columns (headers are matched case-insensitively):
        - Название / Name
        - Артикул (SKU) / SKU
        - Категория / Category
        - Ед. изм. / Unit
        - Количество / Quantity
        - Мин. остаток / MinQuantity
        - Цена за ед. / Price
        - Место хранения / Location
        - Описание / Description
    """

    from openpyxl import load_workbook

    raw = await file.read()
    try:
        wb = load_workbook(filename=BytesIO(raw), data_only=True)
    except Exception as exc:
        return WarehouseItemsImportResponse(
            created_count=0,
            updated_count=0,
            skipped_count=0,
            error_count=1,
            errors=[f"Failed to read XLSX: {exc}"],
        )

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return WarehouseItemsImportResponse(
            created_count=0,
            updated_count=0,
            skipped_count=0,
            error_count=1,
            errors=["Empty sheet"],
        )

    header_row = rows[0]
    headers_norm = [
        (str(h).strip().lower() if h is not None else "") for h in header_row
    ]

    aliases_to_field: dict[str, str] = {
        "название": "name",
        "наименование": "name",
        "name": "name",
        "артикул": "sku",
        "артикул (sku)": "sku",
        "sku": "sku",
        "код": "sku",
        "категория": "category",
        "category": "category",
        "ед. изм.": "unit",
        "ед. изм": "unit",
        "ед. изм. ": "unit",
        "unit": "unit",
        "единица": "unit",
        "количество": "quantity",
        "quantity": "quantity",
        "кол-во": "quantity",
        "мин. остаток": "min_quantity",
        "min остаток": "min_quantity",
        "minquantity": "min_quantity",
        "min_quantity": "min_quantity",
        "цена за ед.": "price",
        "цена за ед": "price",
        "цена": "price",
        "price": "price",
        "место хранения": "location",
        "location": "location",
        "склад": "location",
        "описание": "description",
        "description": "description",
    }

    def _norm_col(v: str) -> str:
        return v.replace("\u00a0", " ").strip().lower()

    col_to_field: dict[int, str] = {}
    for idx, h in enumerate(headers_norm):
        nh = _norm_col(h)
        if nh in aliases_to_field:
            col_to_field[idx] = aliases_to_field[nh]

    def _to_decimal(v: object) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            s = str(v).strip().replace(",", ".")
            if s == "":
                return None
            return Decimal(s)
        except Exception:
            return None

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors: list[str] = []

    # Cache existing SKUs to minimize per-row queries.
    sku_col_indexes = [idx for idx, f in col_to_field.items() if f == "sku"]
    sku_idx = sku_col_indexes[0] if sku_col_indexes else None
    existing_by_sku: dict[str, WarehouseItem] = {}
    if sku_idx is not None:
        skus_in_sheet: set[str] = set()
        for r in rows[1:]:
            if sku_idx >= len(r):
                continue
            raw_sku = r[sku_idx]
            if raw_sku is None:
                continue
            s = str(raw_sku).strip()
            if s:
                skus_in_sheet.add(s)
        if skus_in_sheet:
            result = await db.execute(select(WarehouseItem).where(WarehouseItem.sku.in_(list(skus_in_sheet))))
            for it in result.scalars().all():
                existing_by_sku[it.sku] = it

    for row_idx, r in enumerate(rows[1:], start=2):
        try:
            if not isinstance(r, tuple):
                continue

            # Required SKU.
            sku_value = None
            if sku_idx is not None and sku_idx < len(r):
                if r[sku_idx] is not None:
                    sku_value = str(r[sku_idx]).strip()

            if not sku_value:
                skipped_count += 1
                continue

            # Read fields by column.
            def _get(field: str) -> object:
                for c_idx, f in col_to_field.items():
                    if f == field and c_idx < len(r):
                        return r[c_idx]
                return None

            name_val = _get("name")
            category_val = _get("category") or "materials"
            unit_val = _get("unit") or "pcs"

            qty = _to_decimal(_get("quantity")) or Decimal("0")
            min_qty = _to_decimal(_get("min_quantity")) or Decimal("0")
            price = _to_decimal(_get("price")) or Decimal("0")

            desc = _get("description")
            location = _get("location")

            name_str = str(name_val).strip() if name_val is not None else ""
            if not name_str:
                skipped_count += 1
                continue

            existing = existing_by_sku.get(sku_value)
            if existing:
                await db.execute(
                    update(WarehouseItem)
                    .where(WarehouseItem.id == existing.id)
                    .values(
                        name=name_str,
                        category=str(category_val).strip() or "materials",
                        unit=str(unit_val).strip() or "pcs",
                        quantity=qty,
                        min_quantity=min_qty,
                        price=price,
                        description=str(desc).strip() if desc not in (None, "") else None,
                        location=str(location).strip() if location not in (None, "") else None,
                    )
                )
                updated_count += 1
            else:
                item = WarehouseItem(
                    name=name_str,
                    sku=sku_value,
                    category=str(category_val).strip() or "materials",
                    unit=str(unit_val).strip() or "pcs",
                    quantity=qty,
                    min_quantity=min_qty,
                    price=price,
                    description=str(desc).strip() if desc not in (None, "") else None,
                    location=str(location).strip() if location not in (None, "") else None,
                )
                db.add(item)
                await db.flush()
                created_count += 1

        except Exception as exc:
            errors.append(f"Row {row_idx}: {exc}")
            skipped_count += 1

    error_count = len(errors)
    return WarehouseItemsImportResponse(
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        error_count=error_count,
        errors=errors[:20],
    )
