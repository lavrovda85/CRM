"""Task management API endpoints.

CRUD операции над задачами, переходы по workflow,
управление чек-листами и смена статусов.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import PaginationParams, get_crm_user_id, get_current_user, get_db
from app.core.exceptions import NotFoundError, ValidationError, WorkflowTransitionError
from app.core.pagination import PaginatedResponse
from app.core.permissions import MANAGE_TASKS, user_sees_all_company_tasks
from app.core.security import CurrentUser
from app.models import (
    Checklist,
    ChecklistItem,
    Comment,
    Document,
    Task,
    TaskStatusHistory,
    TaskTemplate,
    TimeEntry,
)
from app.services.task_notification_service import TaskNotificationService
from app.services.task_service import TaskService
from app.services.user_identity import resolve_users_table_id
from app.schemas.task import (
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskDetail,
    TaskResponse,
    TaskStatusTransition,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks")

_TERMINAL_TASK_STATUSES = ("done", "completed", "closed")


def _task_row_visibility(user: CurrentUser, crm_uid: uuid.UUID):
    """SQL predicate: which task rows the current user may access."""
    return TaskService.sql_tasks_row_visible(
        crm_uid,
        user_sees_all=user_sees_all_company_tasks(user),
    )


def _tasks_search_clause(q: str | None):
    """Build OR(title ILIKE, description ILIKE) for non-empty trimmed query."""
    raw = (q or "").strip()
    if not raw:
        return None
    term = f"%{raw[:200]}%"
    return or_(Task.title.ilike(term), Task.description.ilike(term))


def _overdue_query_active(overdue: str | None) -> bool:
    """True when client sends overdue=1|true|yes|on (case-insensitive)."""
    if overdue is None or overdue == "":
        return False
    return overdue.lower() in ("1", "true", "yes", "on")


def _parse_csv_param(raw: str | None) -> list[str]:
    """Split comma-separated non-empty tokens (status filters, etc.)."""
    if not raw or not str(raw).strip():
        return []
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def _merge_geo_into_custom_fields(
    custom_fields: dict | None,
    *,
    address: str | None,
    latitude: float | None,
    longitude: float | None,
) -> dict:
    """Merge typed geo fields into task custom_fields payload."""
    merged: dict = dict(custom_fields or {})
    if address is not None:
        if str(address).strip():
            merged["address"] = str(address).strip()
        else:
            merged.pop("address", None)
    if latitude is not None:
        merged["latitude"] = float(latitude)
    if longitude is not None:
        merged["longitude"] = float(longitude)
    return merged


def _task_response_load_options():
    """ORM loader options for Task -> TaskResponse without async lazy loads.

    Возвращает:
        Кортеж опций selectinload для связей assignee и template,
        которые иначе вызвали бы ленивую загрузку при model_validate
        и привели бы к MissingGreenlet в async-сессии.
    """
    return (
        selectinload(Task.assignee),
        selectinload(Task.template),
        selectinload(Task.creator),
        selectinload(Task.requester_user),
        selectinload(Task.co_assignees),
        selectinload(Task.observers),
    )


def _task_detail_load_options():
    """ORM loader options for Task -> TaskDetail without async lazy loads."""
    return (
        selectinload(Task.checklists).selectinload(Checklist.items),
        selectinload(Task.comments).selectinload(Comment.author),
        selectinload(Task.documents),
        selectinload(Task.time_entries),
        selectinload(Task.status_history),
        *_task_response_load_options(),
    )


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    creator_id: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> TaskResponse:
    """Create a new task from template or ad-hoc.

    Создаёт задачу на основе шаблона (если указан template_id)
    или произвольную задачу. При создании из шаблона копирует
    чек-листы и устанавливает начальный статус из workflow.

    Аргументы:
        body: Данные для создания задачи.
        db: Асинхронная сессия БД.
        creator_id: Внутренний ``users.id`` создателя (из JWT / Keycloak).

    Возвращает:
        Созданную задачу.
    """
    initial_status = "new"

    if body.template_id:
        result = await db.execute(
            select(TaskTemplate)
            .options(selectinload(TaskTemplate.checklists))
            .where(
                TaskTemplate.id == body.template_id,
                TaskTemplate.company_id == ctx.company_id,
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError("TaskTemplate", str(body.template_id))
        wf = template.workflow_definition or {}
        initial_status = wf.get("initial_state", "new")

    task = Task(
        company_id=ctx.company_id,
        template_id=body.template_id,
        board_id=body.board_id,
        client_id=body.client_id,
        deal_id=body.deal_id,
        tender_id=body.tender_id,
        assigned_to=body.assigned_to,
        created_by=creator_id,
        requested_by=body.requested_by,
        title=body.title,
        description=body.description,
        status=initial_status,
        priority=body.priority,
        custom_fields=_merge_geo_into_custom_fields(
            body.custom_fields,
            address=body.address,
            latitude=body.latitude,
            longitude=body.longitude,
        ),
        due_date=body.due_date,
        started_at=body.started_at,
        visibility=body.visibility,
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
    if body.co_assignee_ids:
        await TaskService.set_co_assignees(db, task.id, list(body.co_assignee_ids))
    if body.observer_ids:
        await TaskService.set_observers(db, task.id, list(body.observer_ids))
    loaded = await db.execute(
        select(Task)
        .options(*_task_response_load_options())
        .where(Task.id == task.id)
    )
    task_for_api = loaded.scalar_one()
    await TaskNotificationService.notify_after_task_created(db, task_for_api, creator_id)
    return TaskResponse.model_validate(task_for_api)


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    status: str | None = Query(default=None, description="Filter by status"),
    status_in: str | None = Query(
        default=None,
        description="Comma-separated statuses (OR). If set, overrides single ``status``.",
    ),
    status_not_in: str | None = Query(
        default=None,
        description="Comma-separated statuses to exclude (e.g. hide closed from main board).",
    ),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by primary assignee"),
    involves_user: uuid.UUID | None = Query(
        default=None,
        description="Tasks where user is primary assignee OR co-assignee",
    ),
    client_id: uuid.UUID | None = Query(default=None, description="Filter by client"),
    board_id: uuid.UUID | None = Query(default=None, description="Filter by board"),
    exclude_board_id: uuid.UUID | None = Query(
        default=None,
        description="Exclude tasks assigned to this board (e.g. hide field-crew board on the office tasks page)",
    ),
    priority: str | None = Query(default=None, description="Filter by priority"),
    q: str | None = Query(default=None, description="Case-insensitive search in title and description"),
    overdue: str | None = Query(
        default=None,
        description="If set (e.g. 1/true), only tasks past due_date and not in a terminal status",
    ),
    due_after: datetime | None = Query(default=None, description="Tasks with due_date >= this (UTC)"),
    due_before: datetime | None = Query(default=None, description="Tasks with due_date <= this (UTC)"),
    updated_after: datetime | None = Query(default=None, description="Tasks with updated_at >= this (UTC)"),
    updated_before: datetime | None = Query(default=None, description="Tasks with updated_at <= this (UTC)"),
    order: str | None = Query(
        default="created_desc",
        description="Sort: created_desc (default) or updated_desc",
    ),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
        q: Поиск по подстроке в названии и описании.
        overdue: Только просроченные нетерминальные задачи.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком задач.
    """
    query = select(Task).options(*_task_response_load_options()).where(
        Task.active_filter(),
        Task.company_id == ctx.company_id,
        _task_row_visibility(user, crm_uid),
    )
    count_query = select(func.count(Task.id)).where(
        Task.active_filter(),
        Task.company_id == ctx.company_id,
        _task_row_visibility(user, crm_uid),
    )

    status_list = _parse_csv_param(status_in)
    if status_list:
        query = query.where(Task.status.in_(status_list))
        count_query = count_query.where(Task.status.in_(status_list))
    elif status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)

    status_excluded = _parse_csv_param(status_not_in)
    if status_excluded:
        query = query.where(Task.status.notin_(status_excluded))
        count_query = count_query.where(Task.status.notin_(status_excluded))

    if involves_user:
        from app.models.task import task_co_assignees, task_observers

        co_exists = (
            select(1)
            .select_from(task_co_assignees)
            .where(
                task_co_assignees.c.task_id == Task.id,
                task_co_assignees.c.user_id == involves_user,
            )
            .exists()
        )
        obs_exists = (
            select(1)
            .select_from(task_observers)
            .where(
                task_observers.c.task_id == Task.id,
                task_observers.c.user_id == involves_user,
            )
            .exists()
        )
        query = query.where(
            (Task.assigned_to == involves_user) | co_exists | obs_exists,
        )
        count_query = count_query.where((Task.assigned_to == involves_user) | co_exists | obs_exists)
    elif assigned_to:
        query = query.where(Task.assigned_to == assigned_to)
        count_query = count_query.where(Task.assigned_to == assigned_to)
    if client_id:
        query = query.where(Task.client_id == client_id)
        count_query = count_query.where(Task.client_id == client_id)
    if board_id:
        query = query.where(Task.board_id == board_id)
        count_query = count_query.where(Task.board_id == board_id)
    if exclude_board_id:
        query = query.where((Task.board_id.is_(None)) | (Task.board_id != exclude_board_id))
        count_query = count_query.where((Task.board_id.is_(None)) | (Task.board_id != exclude_board_id))
    if priority:
        query = query.where(Task.priority == priority)
        count_query = count_query.where(Task.priority == priority)

    search_clause = _tasks_search_clause(q)
    if search_clause is not None:
        query = query.where(search_clause)
        count_query = count_query.where(search_clause)

    if _overdue_query_active(overdue):
        now = datetime.now(timezone.utc)
        overdue_cond = (
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.notin_(_TERMINAL_TASK_STATUSES),
        )
        query = query.where(*overdue_cond)
        count_query = count_query.where(*overdue_cond)

    if due_after is not None:
        query = query.where(Task.due_date.isnot(None), Task.due_date >= due_after)
        count_query = count_query.where(Task.due_date.isnot(None), Task.due_date >= due_after)
    if due_before is not None:
        query = query.where(Task.due_date.isnot(None), Task.due_date <= due_before)
        count_query = count_query.where(Task.due_date.isnot(None), Task.due_date <= due_before)
    if updated_after is not None:
        query = query.where(Task.updated_at >= updated_after)
        count_query = count_query.where(Task.updated_at >= updated_after)
    if updated_before is not None:
        query = query.where(Task.updated_at <= updated_before)
        count_query = count_query.where(Task.updated_at <= updated_before)

    order_norm = (order or "created_desc").strip().lower()
    order_col = Task.updated_at.desc() if order_norm == "updated_desc" else Task.created_at.desc()

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(order_col)
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


@router.get("/deleted", response_model=PaginatedResponse[TaskResponse])
async def list_deleted_tasks(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(MANAGE_TASKS),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> PaginatedResponse[TaskResponse]:
    """List soft-deleted tasks (trash) for recovery; admin/manager only.

    Returns tasks with ``deleted_at`` set, newest first.
    """
    tasks, total = await TaskService.list_deleted_tasks(
        db,
        company_id=ctx.company_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
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
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
        .options(*_task_detail_load_options())
        .where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
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
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> TaskResponse:
    """Update task fields.

    Частичное обновление полей задачи. Передаются только
    изменяемые поля.

    Аргументы:
        task_id: UUID задачи.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        crm_uid: Внутренний ``users.id`` для истории.

    Возвращает:
        Обновлённую задачу.
    """
    result = await db.execute(
        select(Task)
        .options(*_task_response_load_options())
        .where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))

    prev_status = task.status
    prev_assignee = task.assigned_to

    update_data = body.model_dump(exclude_unset=True)
    geo_address = update_data.pop("address", None) if "address" in update_data else None
    geo_lat = update_data.pop("latitude", None) if "latitude" in update_data else None
    geo_lng = update_data.pop("longitude", None) if "longitude" in update_data else None
    if any(k in body.model_fields_set for k in ("address", "latitude", "longitude")):
        merged_geo = _merge_geo_into_custom_fields(
            update_data.get("custom_fields", task.custom_fields),
            address=geo_address if "address" in body.model_fields_set else None,
            latitude=geo_lat if "latitude" in body.model_fields_set else None,
            longitude=geo_lng if "longitude" in body.model_fields_set else None,
        )
        if "latitude" in body.model_fields_set and geo_lat is None:
            merged_geo.pop("latitude", None)
        if "longitude" in body.model_fields_set and geo_lng is None:
            merged_geo.pop("longitude", None)
        if "address" in body.model_fields_set and (geo_address is None or not str(geo_address).strip()):
            merged_geo.pop("address", None)
        update_data["custom_fields"] = merged_geo
    co_unset = "co_assignee_ids" not in update_data
    notify_co_assignees_changed = not co_unset
    if not co_unset:
        co_assignee_ids = update_data.pop("co_assignee_ids")

    obs_unset = "observer_ids" not in update_data
    if not obs_unset:
        observer_ids = update_data.pop("observer_ids")

    # Auto-status and history when assigning executor via properties.
    assigned_to = update_data.get("assigned_to")
    assignee_changed = assigned_to is not None and assigned_to != prev_assignee

    # If задача была в статусе new и ей назначили исполнителя, считаем её назначенной.
    new_status = prev_status
    if assignee_changed and prev_status == "new":
        new_status = "dispatched"
        update_data["status"] = "dispatched"

    if update_data:
        await db.execute(
            update(Task).where(Task.id == task_id).values(**update_data)
        )
        await db.flush()

        # История назначения (даже если статус не изменился).
        if assignee_changed:
            db.add(TaskStatusHistory(
                task_id=task_id,
                from_status=prev_status,
                to_status=new_status,
                changed_by=crm_uid,
                reason="Assignee changed via task properties",
                transition_data={
                    "from_assigned_to": str(prev_assignee) if prev_assignee else None,
                    "to_assigned_to": str(assigned_to),
                },
            ))
            await db.flush()

    if not co_unset:
        await TaskService.set_co_assignees(db, task_id, list(co_assignee_ids or []))
    if not obs_unset:
        await TaskService.set_observers(db, task_id, list(observer_ids or []))

    loaded = await db.execute(
        select(Task)
        .options(*_task_response_load_options())
        .where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    task_for_api = loaded.scalar_one_or_none()
    if not task_for_api:
        raise NotFoundError("Task", str(task_id))

    if assignee_changed:
        await TaskNotificationService.notify_assignee_change(
            db,
            task_for_api,
            prev_assignee=prev_assignee,
            new_assignee=task_for_api.assigned_to,
            actor_id=crm_uid,
        )
    notify_changed = {k for k in ("due_date", "priority", "title") if k in update_data}
    if notify_co_assignees_changed:
        notify_changed.add("co_assignees")
    if notify_changed:
        await TaskNotificationService.notify_task_fields_changed(
            db,
            task_for_api,
            actor_id=crm_uid,
            changed=notify_changed,
        )

    return TaskResponse.model_validate(task_for_api)


@router.post("/{task_id}/restore", response_model=TaskResponse)
async def restore_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(MANAGE_TASKS),
) -> TaskResponse:
    """Restore a soft-deleted task (admin/manager)."""
    uid = await resolve_users_table_id(db, user)
    await TaskService.restore_task(db, task_id, {"id": uid})
    loaded = await db.execute(
        select(Task)
        .options(*_task_response_load_options())
        .where(Task.id == task_id, Task.active_filter())
    )
    task_for_api = loaded.scalar_one_or_none()
    if not task_for_api:
        raise NotFoundError("Task", str(task_id))
    return TaskResponse.model_validate(task_for_api)


@router.post("/{task_id}/transition", response_model=TaskResponse)
async def transition_task(
    task_id: uuid.UUID,
    body: TaskStatusTransition,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> TaskResponse:
    """Change task status through workflow transition.

    Выполняет переход задачи в новый статус. Валидирует
    допустимость перехода на основе workflow_definition шаблона
    и проверяет заполненность gate-чек-листов.

    Аргументы:
        task_id: UUID задачи.
        body: Данные перехода (целевой статус и причина).
        db: Асинхронная сессия БД.
        crm_uid: Внутренний ``users.id`` для истории статусов.

    Возвращает:
        Задачу с обновлённым статусом.
    """
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.checklists).selectinload(Checklist.items),
            *_task_response_load_options(),
        )
        .where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))

    from_status = task.status
    to_status = body.to_status

    backwards_allowed_without_workflow_gate = False

    if task.template_id:
        tmpl_result = await db.execute(
            select(TaskTemplate).where(TaskTemplate.id == task.template_id)
        )
        template = tmpl_result.scalar_one_or_none()
        if template and template.workflow_definition:
            transitions = template.workflow_definition.get("transitions", [])
            states = template.workflow_definition.get("states") or []
            order: dict[str, int] = {name: idx for idx, name in enumerate(states)}

            is_backwards = (
                from_status in order
                and to_status in order
                and order[to_status] < order[from_status]
            )

            allowed = [
                t for t in transitions
                if t.get("from") == from_status and t.get("to") == to_status
            ]

            if not allowed and not is_backwards:
                # Forward transition not declared in workflow_definition.
                raise WorkflowTransitionError(
                    task_id=str(task_id),
                    from_status=from_status,
                    to_status=to_status,
                    reason="Transition not allowed by workflow definition",
                )

            # Для обратных переходов (возврат задачи назад по колонкам)
            # разрешаем смену статуса даже если переход не описан
            # в workflow_definition и не проверяем gate-чек-листы.
            if is_backwards and not allowed:
                backwards_allowed_without_workflow_gate = True

    if not backwards_allowed_without_workflow_gate:
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
        changed_by=crm_uid,
        reason=body.reason,
        transition_data=body.checklist_data or {},
    ))

    await db.flush()
    loaded = await db.execute(
        select(Task)
        .options(*_task_response_load_options())
        .where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    task_for_api = loaded.scalar_one()
    await TaskNotificationService.notify_observers_status_changed(
        db,
        task_for_api,
        actor_id=crm_uid,
        from_status=from_status,
        to_status=to_status,
    )
    return TaskResponse.model_validate(task_for_api)


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
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
    tchk = await db.execute(
        select(Task.id).where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    if tchk.scalar_one_or_none() is None:
        raise NotFoundError("Task", str(task_id))

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
            completed_by=crm_uid if new_state else None,
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

    return await get_task(task_id, db, user, crm_uid, ctx)


@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    task_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> CommentResponse:
    """Add a comment to a task.

    Создаёт комментарий к задаче от имени текущего пользователя.

    Аргументы:
        task_id: UUID задачи.
        body: Текст и упоминания комментария.
        db: Асинхронная сессия БД.
        crm_uid: Внутренний ``users.id`` автора.

    Возвращает:
        Созданный комментарий.
    """
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task", str(task_id))

    clean_body = (body.body or "").strip()
    attachment_ids = body.attachment_doc_ids or []
    if not clean_body and not attachment_ids:
        raise ValidationError("body", "Empty comment. Provide text or attachments.")

    # Validate attachment docs belong to this task.
    attachment_ids_str = [str(x) for x in attachment_ids]
    if attachment_ids:
        doc_q = select(Document.id).where(Document.id.in_(attachment_ids), Document.task_id == task_id)
        doc_res = await db.execute(doc_q)
        doc_ids = {str(x) for x in doc_res.scalars().all()}
        missing = [str(x) for x in attachment_ids if str(x) not in doc_ids]
        if missing:
            raise ValidationError("attachment_doc_ids", f"Some attachments are not linked to task: {missing}")

    comment = Comment(
        task_id=task_id,
        author_id=crm_uid,
        body=clean_body,
        mentions=[str(m) for m in body.mentions],
        attachments=attachment_ids_str,
    )
    db.add(comment)
    await db.flush()
    loaded = (
        await db.execute(
            select(Comment).options(selectinload(Comment.author)).where(Comment.id == comment.id),
        )
    ).scalar_one()
    return CommentResponse.model_validate(loaded)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    crm_uid: uuid.UUID = Depends(get_crm_user_id),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> None:
    """Soft-delete a task: hidden from lists and analytics; history kept for restore.

    Аргументы:
        task_id: UUID задачи.
        db: Асинхронная сессия БД.
        crm_uid: Внутренний ``users.id`` для soft-delete аудита.
    """
    chk = await db.execute(
        select(Task.id).where(
            Task.id == task_id,
            Task.active_filter(),
            Task.company_id == ctx.company_id,
            _task_row_visibility(user, crm_uid),
        )
    )
    if chk.scalar_one_or_none() is None:
        raise NotFoundError("Task", str(task_id))
    await TaskService.delete_task(db, task_id, {"id": crm_uid})
