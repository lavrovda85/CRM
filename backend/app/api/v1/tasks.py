"""Task management API endpoints.

CRUD операции над задачами, переходы по workflow,
управление чек-листами и смена статусов.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError, WorkflowTransitionError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import (
    Checklist,
    ChecklistItem,
    Task,
    TaskStatusHistory,
    TaskTemplate,
)
from app.schemas.task import (
    TaskCreate,
    TaskDetail,
    TaskResponse,
    TaskStatusTransition,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks")


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskResponse:
    """Create a new task from template or ad-hoc.

    Создаёт задачу на основе шаблона (если указан template_id)
    или произвольную задачу. При создании из шаблона копирует
    чек-листы и устанавливает начальный статус из workflow.

    Аргументы:
        body: Данные для создания задачи.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную задачу.
    """
    initial_status = "new"

    if body.template_id:
        result = await db.execute(
            select(TaskTemplate)
            .options(selectinload(TaskTemplate.checklists))
            .where(TaskTemplate.id == body.template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError("TaskTemplate", str(body.template_id))
        wf = template.workflow_definition or {}
        initial_status = wf.get("initial_state", "new")

    task = Task(
        template_id=body.template_id,
        board_id=body.board_id,
        client_id=body.client_id,
        deal_id=body.deal_id,
        tender_id=body.tender_id,
        assigned_to=body.assigned_to,
        created_by=uuid.UUID(user.sub) if user.sub else None,
        title=body.title,
        description=body.description,
        status=initial_status,
        priority=body.priority,
        custom_fields=body.custom_fields,
        due_date=body.due_date,
    )
    db.add(task)
    await db.flush()

    if body.template_id and template:
        for tc in template.checklists:
            checklist = Checklist(
                task_id=task.id,
                title=tc.title,
                gate_transition=tc.gate_transition,
            )
            db.add(checklist)
            await db.flush()
            for idx, item_data in enumerate(tc.items or []):
                title = item_data if isinstance(item_data, str) else item_data.get("title", "")
                db.add(ChecklistItem(
                    checklist_id=checklist.id,
                    title=title,
                    order=idx,
                ))

    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.get("/", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assignee"),
    client_id: uuid.UUID | None = Query(default=None, description="Filter by client"),
    board_id: uuid.UUID | None = Query(default=None, description="Filter by board"),
    priority: str | None = Query(default=None, description="Filter by priority"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[TaskResponse]:
    """List tasks with optional filters.

    Возвращает постраничный список задач с фильтрацией
    по статусу, исполнителю, клиенту, доске и приоритету.

    Аргументы:
        status: Фильтр по статусу задачи.
        assigned_to: Фильтр по ID исполнителя.
        client_id: Фильтр по ID клиента.
        board_id: Фильтр по ID доски.
        priority: Фильтр по приоритету.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком задач.
    """
    query = select(Task)
    count_query = select(func.count(Task.id))

    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    if assigned_to:
        query = query.where(Task.assigned_to == assigned_to)
        count_query = count_query.where(Task.assigned_to == assigned_to)
    if client_id:
        query = query.where(Task.client_id == client_id)
        count_query = count_query.where(Task.client_id == client_id)
    if board_id:
        query = query.where(Task.board_id == board_id)
        count_query = count_query.where(Task.board_id == board_id)
    if priority:
        query = query.where(Task.priority == priority)
        count_query = count_query.where(Task.priority == priority)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Task.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    tasks = result.scalars().all()

    return PaginatedResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskDetail:
    """Get task detail with checklists, comments and documents.

    Возвращает полную информацию о задаче, включая
    чек-листы с пунктами и комментарии.

    Аргументы:
        task_id: UUID задачи.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о задаче.
    """
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.checklists).selectinload(Checklist.items),
            selectinload(Task.comments),
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))
    return TaskDetail.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskResponse:
    """Update task fields.

    Частичное обновление полей задачи. Передаются только
    изменяемые поля.

    Аргументы:
        task_id: UUID задачи.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую задачу.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))

    update_data = body.model_dump(exclude_unset=True)
    if update_data:
        await db.execute(
            update(Task).where(Task.id == task_id).values(**update_data)
        )
        await db.flush()
        await db.refresh(task)

    return TaskResponse.model_validate(task)


@router.post("/{task_id}/transition", response_model=TaskResponse)
async def transition_task(
    task_id: uuid.UUID,
    body: TaskStatusTransition,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskResponse:
    """Change task status through workflow transition.

    Выполняет переход задачи в новый статус. Валидирует
    допустимость перехода на основе workflow_definition шаблона
    и проверяет заполненность gate-чек-листов.

    Аргументы:
        task_id: UUID задачи.
        body: Данные перехода (целевой статус и причина).
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Задачу с обновлённым статусом.
    """
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.checklists).selectinload(Checklist.items))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))

    from_status = task.status
    to_status = body.to_status

    if task.template_id:
        tmpl_result = await db.execute(
            select(TaskTemplate).where(TaskTemplate.id == task.template_id)
        )
        template = tmpl_result.scalar_one_or_none()
        if template and template.workflow_definition:
            transitions = template.workflow_definition.get("transitions", [])
            allowed = [
                t for t in transitions
                if t.get("from") == from_status and t.get("to") == to_status
            ]
            if not allowed:
                raise WorkflowTransitionError(
                    task_id=str(task_id),
                    from_status=from_status,
                    to_status=to_status,
                    reason="Transition not allowed by workflow definition",
                )

    transition_key = f"{from_status}->{to_status}"
    for checklist in task.checklists:
        if checklist.gate_transition == transition_key and not checklist.is_completed:
            incomplete = [i for i in checklist.items if not i.is_completed]
            if incomplete:
                raise WorkflowTransitionError(
                    task_id=str(task_id),
                    from_status=from_status,
                    to_status=to_status,
                    reason=f"Checklist '{checklist.title}' has incomplete items",
                )

    now = datetime.now(timezone.utc)
    values: dict = {"status": to_status}
    if to_status in ("in_progress",) and not task.started_at:
        values["started_at"] = now
    if to_status in ("completed", "done", "closed"):
        values["completed_at"] = now

    await db.execute(update(Task).where(Task.id == task_id).values(**values))

    db.add(TaskStatusHistory(
        task_id=task_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=uuid.UUID(user.sub),
        reason=body.reason,
        transition_data=body.checklist_data or {},
    ))

    await db.flush()
    await db.refresh(task)
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/checklists/{checklist_id}/items/{item_id}/toggle",
    response_model=TaskDetail,
)
async def toggle_checklist_item(
    task_id: uuid.UUID,
    checklist_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskDetail:
    """Toggle a checklist item completion state.

    Переключает состояние пункта чек-листа (выполнен/не выполнен).
    Автоматически обновляет is_completed чек-листа если все пункты выполнены.

    Аргументы:
        task_id: UUID задачи.
        checklist_id: UUID чек-листа.
        item_id: UUID пункта чек-листа.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённую детальную информацию о задаче.
    """
    result = await db.execute(
        select(ChecklistItem)
        .join(Checklist, ChecklistItem.checklist_id == Checklist.id)
        .where(
            Checklist.task_id == task_id,
            ChecklistItem.checklist_id == checklist_id,
            ChecklistItem.id == item_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("ChecklistItem", str(item_id))

    now = datetime.now(timezone.utc)
    new_state = not item.is_completed
    await db.execute(
        update(ChecklistItem)
        .where(ChecklistItem.id == item_id)
        .values(
            is_completed=new_state,
            completed_by=uuid.UUID(user.sub) if new_state else None,
            completed_at=now if new_state else None,
        )
    )

    all_items_result = await db.execute(
        select(ChecklistItem).where(ChecklistItem.checklist_id == checklist_id)
    )
    all_items = all_items_result.scalars().all()
    all_completed = all(
        (i.is_completed if i.id != item_id else new_state) for i in all_items
    )
    await db.execute(
        update(Checklist)
        .where(Checklist.id == checklist_id)
        .values(is_completed=all_completed)
    )
    await db.flush()

    return await get_task(task_id, db, user)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a task by ID.

    Удаляет задачу и все связанные данные (чек-листы,
    комментарии) каскадно.

    Аргументы:
        task_id: UUID задачи.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))
    await db.delete(task)
    await db.flush()
