"""Reference dictionary management API endpoints.

CRUD операции над динамическими справочниками
и их элементами.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import DuplicateError, NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Reference, ReferenceItem
from app.schemas.reference import (
    ReferenceCreate,
    ReferenceItemCreate,
    ReferenceItemResponse,
    ReferenceItemUpdate,
    ReferenceResponse,
)

router = APIRouter(prefix="/references")


@router.post("/", response_model=ReferenceResponse, status_code=201)
async def create_reference(
    body: ReferenceCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ReferenceResponse:
    """Create a new reference dictionary.

    Создаёт новый справочник с уникальным кодом.

    Аргументы:
        body: Данные справочника.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный справочник.
    """
    existing = await db.execute(
        select(Reference).where(Reference.code == body.code)
    )
    if existing.scalar_one_or_none():
        raise DuplicateError("Reference", "code", body.code)

    ref = Reference(
        code=body.code,
        name=body.name,
        description=body.description,
        is_system=body.is_system,
    )
    db.add(ref)
    await db.flush()
    await db.refresh(ref, attribute_names=["items"])
    return ReferenceResponse.model_validate(ref)


@router.get("/", response_model=PaginatedResponse[ReferenceResponse])
async def list_references(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[ReferenceResponse]:
    """List all reference dictionaries.

    Возвращает постраничный список всех справочников
    без элементов (для компактности).

    Аргументы:
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком справочников.
    """
    count_query = select(func.count(Reference.id))
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(
        select(Reference)
        .options(selectinload(Reference.items))
        .order_by(Reference.code)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    refs = result.scalars().unique().all()

    return PaginatedResponse(
        items=[ReferenceResponse.model_validate(r) for r in refs],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{code}", response_model=ReferenceResponse)
async def get_reference(
    code: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ReferenceResponse:
    """Get reference dictionary with all items.

    Возвращает справочник по его коду вместе
    со всеми элементами, отсортированными по order.

    Аргументы:
        code: Машинное имя справочника.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Справочник с элементами.
    """
    result = await db.execute(
        select(Reference)
        .options(selectinload(Reference.items))
        .where(Reference.code == code)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise NotFoundError("Reference", code)
    return ReferenceResponse.model_validate(ref)


@router.post("/{code}/items", response_model=ReferenceItemResponse, status_code=201)
async def add_item(
    code: str,
    body: ReferenceItemCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ReferenceItemResponse:
    """Add an item to a reference dictionary.

    Добавляет новый элемент в справочник по его коду.

    Аргументы:
        code: Машинное имя справочника.
        body: Данные элемента.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный элемент справочника.
    """
    result = await db.execute(
        select(Reference).where(Reference.code == code)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise NotFoundError("Reference", code)

    existing_item = await db.execute(
        select(ReferenceItem).where(
            ReferenceItem.reference_id == ref.id,
            ReferenceItem.code == body.code,
        )
    )
    if existing_item.scalar_one_or_none():
        raise DuplicateError("ReferenceItem", "code", body.code)

    item = ReferenceItem(
        reference_id=ref.id,
        code=body.code,
        name=body.name,
        metadata=body.metadata,
        order=body.order,
        is_active=body.is_active,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return ReferenceItemResponse.model_validate(item)


@router.patch("/{code}/items/{item_id}", response_model=ReferenceItemResponse)
async def update_item(
    code: str,
    item_id: uuid.UUID,
    body: ReferenceItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ReferenceItemResponse:
    """Update a reference item.

    Частичное обновление элемента справочника.

    Аргументы:
        code: Машинное имя справочника.
        item_id: UUID элемента.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый элемент.
    """
    result = await db.execute(
        select(Reference).where(Reference.code == code)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise NotFoundError("Reference", code)

    item_result = await db.execute(
        select(ReferenceItem).where(
            ReferenceItem.id == item_id,
            ReferenceItem.reference_id == ref.id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("ReferenceItem", str(item_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(ReferenceItem)
            .where(ReferenceItem.id == item_id)
            .values(**update_data)
        )
        await db.flush()
        await db.refresh(item)

    return ReferenceItemResponse.model_validate(item)


@router.delete("/{code}/items/{item_id}", status_code=204)
async def delete_item(
    code: str,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a reference item.

    Удаляет элемент из справочника. Системные справочники
    не могут быть удалены.

    Аргументы:
        code: Машинное имя справочника.
        item_id: UUID элемента.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(
        select(Reference).where(Reference.code == code)
    )
    ref = result.scalar_one_or_none()
    if not ref:
        raise NotFoundError("Reference", code)

    item_result = await db.execute(
        select(ReferenceItem).where(
            ReferenceItem.id == item_id,
            ReferenceItem.reference_id == ref.id,
        )
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("ReferenceItem", str(item_id))

    await db.delete(item)
    await db.flush()
