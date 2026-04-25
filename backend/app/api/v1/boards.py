"""Board management API endpoints.

CRUD операции над Kanban/Scrum досками
с группировкой задач по статусам.
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import PaginationParams, get_crm_user_id, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.permissions import MANAGE_TASKS, READ_TASKS, user_sees_all_company_tasks
from app.core.security import CurrentUser
from app.models import Board, Task
from app.schemas.board import (
    BoardCreate,
    BoardDetailResponse,
    BoardResponse,
    BoardUpdate,
)
from app.schemas.task import TaskResponse
from app.services.task_service import TaskService
from app.services.user_identity import resolve_users_table_id

router = APIRouter(prefix="/boards")


@router.post("", response_model=BoardResponse, status_code=201)
async def create_board(
    body: BoardCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(MANAGE_TASKS),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> BoardResponse:
    """Create a new board.

    Создаёт Kanban или Scrum доску для группировки
    и визуализации задач.

    Аргументы:
        body: Данные для создания доски.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную доску.
    """
    owner_id = await resolve_users_table_id(db, user)
    board = Board(
        company_id=ctx.company_id,
        name=body.name,
        description=body.description,
        board_type=body.board_type,
        owner_id=owner_id,
        columns=body.columns,
    )
    db.add(board)
    await db.flush()
    await db.refresh(board)
    return BoardResponse.model_validate(board)


@router.get("", response_model=PaginatedResponse[BoardResponse])
async def list_boards(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(READ_TASKS),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> PaginatedResponse[BoardResponse]:
    """List boards for the active company (non-archived).

    Аргументы:
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком досок.
    """
    count_query = (
        select(func.count(Board.id))
        .where(Board.company_id == ctx.company_id, Board.is_archived.is_(False))
    )
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(
        select(Board)
        .where(Board.company_id == ctx.company_id, Board.is_archived.is_(False))
        .order_by(Board.name)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    boards = result.scalars().all()

    return PaginatedResponse(
        items=[BoardResponse.model_validate(b) for b in boards],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{board_id}", response_model=BoardDetailResponse)
async def get_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(READ_TASKS),
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> BoardDetailResponse:
    """Get board detail with tasks grouped by status.

    Возвращает полную информацию о доске, включая
    все задачи, сгруппированные по текущему статусу.

    Аргументы:
        board_id: UUID доски.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о доске с задачами.
    """
    result = await db.execute(
        select(Board)
        .options(
            selectinload(Board.tasks).selectinload(Task.assignee),
            selectinload(Board.tasks).selectinload(Task.template),
            selectinload(Board.tasks).selectinload(Task.creator),
            selectinload(Board.tasks).selectinload(Task.requester_user),
            selectinload(Board.tasks).selectinload(Task.co_assignees),
            selectinload(Board.tasks).selectinload(Task.observers),
        )
        .where(Board.id == board_id, Board.company_id == ctx.company_id)
    )
    board = result.scalar_one_or_none()
    if not board:
        raise NotFoundError("Board", str(board_id))

    tasks_by_status: dict[str, list] = defaultdict(list)
    for task in board.tasks:
        if task.deleted_at is not None:
            continue
        if not TaskService.user_can_view_task(
            task,
            crm_uid,
            user_sees_all=user_sees_all_company_tasks(user),
        ):
            continue
        tasks_by_status[task.status].append(
            TaskResponse.model_validate(task).model_dump()
        )

    board_data = BoardResponse.model_validate(board).model_dump()
    board_data["tasks_by_status"] = dict(tasks_by_status)
    return BoardDetailResponse(**board_data)


@router.patch("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: uuid.UUID,
    body: BoardUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(MANAGE_TASKS),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> BoardResponse:
    """Update board fields.

    Частичное обновление полей доски (название,
    описание, колонки, архивация).

    Аргументы:
        board_id: UUID доски.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую доску.
    """
    result = await db.execute(
        select(Board).where(Board.id == board_id, Board.company_id == ctx.company_id),
    )
    board = result.scalar_one_or_none()
    if not board:
        raise NotFoundError("Board", str(board_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Board).where(Board.id == board_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(board)

    return BoardResponse.model_validate(board)


@router.delete("/{board_id}", status_code=204)
async def delete_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(MANAGE_TASKS),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> None:
    """Delete a board.

    Удаляет доску. Задачи, привязанные к доске,
    не удаляются — обнуляется их board_id.

    Аргументы:
        board_id: UUID доски.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(
        select(Board).where(Board.id == board_id, Board.company_id == ctx.company_id),
    )
    board = result.scalar_one_or_none()
    if not board:
        raise NotFoundError("Board", str(board_id))

    await db.execute(
        update(Task).where(Task.board_id == board_id, Task.company_id == ctx.company_id).values(board_id=None)
    )
    await db.delete(board)
    await db.flush()
