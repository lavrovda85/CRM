"""Time tracking API endpoints.

Управление записями рабочего времени: ручной ввод,
таймер (старт/стоп), сводка по периоду.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import TimeEntry, User
from app.schemas.time_entry import (
    TimeEntryCreate,
    TimeEntryResponse,
    TimeEntryUpdate,
    TimerStart,
    TimerStop,
)

router = APIRouter(prefix="/time")


@router.post("/entries", response_model=TimeEntryResponse, status_code=201)
async def create_time_entry(
    body: TimeEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TimeEntryResponse:
    """Create a manual time entry.

    Создаёт запись рабочего времени (ручной ввод).
    Если указаны started_at и ended_at, автоматически
    рассчитывает duration_minutes.

    Аргументы:
        body: Данные записи времени.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную запись рабочего времени.
    """
    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    duration = body.duration_minutes or 0
    if body.started_at and body.ended_at:
        delta = body.ended_at - body.started_at
        duration = int(delta.total_seconds() / 60)

    entry = TimeEntry(
        task_id=body.task_id,
        user_id=db_user.id,
        started_at=body.started_at,
        ended_at=body.ended_at,
        duration_minutes=duration,
        entry_type=body.entry_type,
        is_billable=body.is_billable,
        notes=body.notes,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return TimeEntryResponse.model_validate(entry)


@router.get("/entries", response_model=PaginatedResponse[TimeEntryResponse])
async def list_time_entries(
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task"),
    user_id: uuid.UUID | None = Query(default=None, description="Filter by user"),
    date_from: date | None = Query(default=None, description="Start of date range"),
    date_to: date | None = Query(default=None, description="End of date range"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[TimeEntryResponse]:
    """List time entries with optional filters.

    Возвращает постраничный список записей времени
    с фильтрацией по задаче, пользователю и диапазону дат.

    Аргументы:
        task_id: Фильтр по ID задачи.
        user_id: Фильтр по ID пользователя.
        date_from: Начало диапазона дат.
        date_to: Конец диапазона дат.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком записей.
    """
    query = select(TimeEntry)
    count_query = select(func.count(TimeEntry.id))

    if task_id:
        query = query.where(TimeEntry.task_id == task_id)
        count_query = count_query.where(TimeEntry.task_id == task_id)
    if user_id:
        query = query.where(TimeEntry.user_id == user_id)
        count_query = count_query.where(TimeEntry.user_id == user_id)
    if date_from:
        dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        query = query.where(TimeEntry.started_at >= dt_from)
        count_query = count_query.where(TimeEntry.started_at >= dt_from)
    if date_to:
        dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
        query = query.where(TimeEntry.started_at <= dt_to)
        count_query = count_query.where(TimeEntry.started_at <= dt_to)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(TimeEntry.started_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    entries = result.scalars().all()

    return PaginatedResponse(
        items=[TimeEntryResponse.model_validate(e) for e in entries],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.patch("/entries/{entry_id}", response_model=TimeEntryResponse)
async def update_time_entry(
    entry_id: uuid.UUID,
    body: TimeEntryUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TimeEntryResponse:
    """Update a time entry.

    Частичное обновление записи рабочего времени.
    Если обновлён ended_at, пересчитывается duration_minutes.

    Аргументы:
        entry_id: UUID записи.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую запись.
    """
    result = await db.execute(select(TimeEntry).where(TimeEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise NotFoundError("TimeEntry", str(entry_id))

    update_data = body.model_dump(exclude_unset=True)
    if "ended_at" in update_data and update_data["ended_at"] and entry.started_at:
        delta = update_data["ended_at"] - entry.started_at
        update_data["duration_minutes"] = int(delta.total_seconds() / 60)

    if update_data:
        await db.execute(
            update(TimeEntry).where(TimeEntry.id == entry_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(entry)

    return TimeEntryResponse.model_validate(entry)


@router.post("/timer/start", response_model=TimeEntryResponse, status_code=201)
async def start_timer(
    body: TimerStart,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TimeEntryResponse:
    """Start a work timer on a task.

    Запускает таймер для задачи. Проверяет, что у пользователя
    нет уже запущенного таймера.

    Аргументы:
        body: Данные для запуска таймера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную запись таймера.
    """
    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    active_timer = await db.execute(
        select(TimeEntry).where(
            and_(
                TimeEntry.user_id == db_user.id,
                TimeEntry.entry_type == "timer",
                TimeEntry.ended_at.is_(None),
            )
        )
    )
    if active_timer.scalar_one_or_none():
        raise ValidationError("timer", "Active timer already running, stop it first")

    entry = TimeEntry(
        task_id=body.task_id,
        user_id=db_user.id,
        started_at=datetime.now(timezone.utc),
        entry_type="timer",
        is_billable=True,
        notes=body.notes,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return TimeEntryResponse.model_validate(entry)


@router.post("/timer/stop", response_model=TimeEntryResponse)
async def stop_timer(
    body: TimerStop,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TimeEntryResponse:
    """Stop the active timer.

    Останавливает текущий запущенный таймер пользователя,
    рассчитывает длительность в минутах.

    Аргументы:
        body: Данные для остановки таймера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую запись таймера с рассчитанной длительностью.
    """
    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    result = await db.execute(
        select(TimeEntry).where(
            and_(
                TimeEntry.user_id == db_user.id,
                TimeEntry.entry_type == "timer",
                TimeEntry.ended_at.is_(None),
            )
        )
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise ValidationError("timer", "No active timer found")

    now = datetime.now(timezone.utc)
    duration = int((now - entry.started_at).total_seconds() / 60) if entry.started_at else 0

    update_values: dict = {"ended_at": now, "duration_minutes": duration}
    if body.notes:
        update_values["notes"] = body.notes

    await db.execute(
        update(TimeEntry).where(TimeEntry.id == entry.id).values(**update_values)
    )
    await db.flush()
    await db.refresh(entry)
    return TimeEntryResponse.model_validate(entry)


@router.get("/summary")
async def get_time_summary(
    user_id: uuid.UUID | None = Query(default=None, description="Filter by user"),
    date_from: date | None = Query(default=None, description="Period start"),
    date_to: date | None = Query(default=None, description="Period end"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get time tracking summary for a user and period.

    Возвращает сводку по трудозатратам: общее количество часов,
    количество записей и разбивку по задачам.

    Аргументы:
        user_id: ID пользователя (по умолчанию — текущий).
        date_from: Начало периода.
        date_to: Конец периода.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Сводку по рабочему времени.
    """
    query = select(
        func.sum(TimeEntry.duration_minutes).label("total_minutes"),
        func.count(TimeEntry.id).label("entries_count"),
    )

    if user_id:
        query = query.where(TimeEntry.user_id == user_id)
    else:
        user_result = await db.execute(
            select(User).where(User.keycloak_id == user.sub)
        )
        db_user = user_result.scalar_one_or_none()
        if db_user:
            query = query.where(TimeEntry.user_id == db_user.id)

    if date_from:
        dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        query = query.where(TimeEntry.started_at >= dt_from)
    if date_to:
        dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)
        query = query.where(TimeEntry.started_at <= dt_to)

    result = await db.execute(query)
    row = result.one()

    total_minutes = row.total_minutes or 0
    return {
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 2),
        "entries_count": row.entries_count or 0,
        "period": {"from": str(date_from) if date_from else None, "to": str(date_to) if date_to else None},
    }
