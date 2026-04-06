"""Client management API endpoints.

CRUD операции над клиентами (физ. лица / организации)
и их контактными лицами.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Client, ClientContact
from app.schemas.client import (
    ClientContactCreate,
    ClientContactResponse,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
)

router = APIRouter(prefix="/clients")


@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    body: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ClientResponse:
    """Create a new client.

    Создаёт нового клиента (физическое лицо или организацию).

    Аргументы:
        body: Данные клиента.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданного клиента.
    """
    client = Client(
        name=body.name,
        client_type=body.client_type,
        address=body.address,
        coordinates=body.coordinates,
        phone=body.phone,
        email=body.email,
        inn=body.inn,
        metadata=body.metadata,
        notes=body.notes,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client, attribute_names=["contacts"])
    return ClientResponse.model_validate(client)


@router.get("/", response_model=PaginatedResponse[ClientResponse])
async def list_clients(
    search: str | None = Query(default=None, description="Search by name, phone or email"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[ClientResponse]:
    """List or search clients.

    Возвращает постраничный список клиентов с возможностью
    поиска по имени, телефону или email.

    Аргументы:
        search: Строка поиска.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком клиентов.
    """
    query = select(Client).options(selectinload(Client.contacts))
    count_query = select(func.count(Client.id))

    if search:
        pattern = f"%{search}%"
        search_filter = or_(
            Client.name.ilike(pattern),
            Client.phone.ilike(pattern),
            Client.email.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Client.name)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    clients = result.scalars().unique().all()

    return PaginatedResponse(
        items=[ClientResponse.model_validate(c) for c in clients],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ClientResponse:
    """Get client detail with contacts.

    Возвращает полную информацию о клиенте,
    включая список контактных лиц.

    Аргументы:
        client_id: UUID клиента.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о клиенте.
    """
    result = await db.execute(
        select(Client)
        .options(selectinload(Client.contacts))
        .where(Client.id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise NotFoundError("Client", str(client_id))
    return ClientResponse.model_validate(client)


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    body: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ClientResponse:
    """Update client fields.

    Частичное обновление данных клиента.

    Аргументы:
        client_id: UUID клиента.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённого клиента.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise NotFoundError("Client", str(client_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Client).where(Client.id == client_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(client, attribute_names=["contacts"])

    return ClientResponse.model_validate(client)


@router.post("/{client_id}/contacts", response_model=ClientContactResponse, status_code=201)
async def add_contact(
    client_id: uuid.UUID,
    body: ClientContactCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ClientContactResponse:
    """Add a contact person to a client.

    Добавляет контактное лицо к клиенту. Если указан
    is_primary=True, снимает признак с предыдущего основного контакта.

    Аргументы:
        client_id: UUID клиента.
        body: Данные контактного лица.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданное контактное лицо.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    if not result.scalar_one_or_none():
        raise NotFoundError("Client", str(client_id))

    if body.is_primary:
        await db.execute(
            update(ClientContact)
            .where(ClientContact.client_id == client_id, ClientContact.is_primary.is_(True))
            .values(is_primary=False)
        )

    contact = ClientContact(
        client_id=client_id,
        full_name=body.full_name,
        position=body.position,
        phone=body.phone,
        email=body.email,
        is_primary=body.is_primary,
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return ClientContactResponse.model_validate(contact)


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a client and all contacts.

    Удаляет клиента и все связанные контактные лица каскадно.

    Аргументы:
        client_id: UUID клиента.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise NotFoundError("Client", str(client_id))
    await db.delete(client)
    await db.flush()
