"""Task template management API endpoints.

CRUD операции над шаблонами задач и создание
задач из шаблонов (инстанцирование).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.permissions import MANAGE_TEMPLATES
from app.core.security import CurrentUser
from app.models import (
    Checklist,
    ChecklistItem,
    Task,
    TaskTemplate,
)
from app.models.task_template import TemplateChecklist
from app.schemas.task import TaskResponse
from app.services.task_service import TaskService
from app.services.user_identity import resolve_users_table_id
from app.schemas.template import (
    InstantiateTemplate,
    TemplateChecklistCreate,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
)

router = APIRouter(prefix="/templates")


def _template_load_options():
    """ORM loader options for TaskTemplate -> TemplateResponse without async lazy loads.

    Возвращает:
        Кортеж selectinload-опций для связей stages/checklists/fields.
    """
    return (
        selectinload(TaskTemplate.stages),
        selectinload(TaskTemplate.checklists),
        selectinload(TaskTemplate.fields),
    )


async def _load_template_for_api(db: AsyncSession, template_id: uuid.UUID) -> TaskTemplate:
    """Load a template with all relations for API response.

    Аргументы:
        db: Асинхронная сессия БД.
        template_id: UUID шаблона.

    Возвращает:
        ORM-объект TaskTemplate с подгруженными связями.
    """
    res = await db.execute(
        select(TaskTemplate).options(*_template_load_options()).where(TaskTemplate.id == template_id)
    )
    template = res.scalar_one_or_none()
    if not template:
        raise NotFoundError("TaskTemplate", str(template_id))
    return template


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TemplateResponse:
    """Create a new task template.

    Создаёт новый шаблон задачи с определением workflow,
    чек-листов, полей и SLA конфигурации.

    Аргументы:
        body: Данные для создания шаблона.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный шаблон.
    """
    template = TaskTemplate(
        name=body.name,
        category=body.category,
        description=body.description,
        workflow_definition=body.workflow_definition,
        required_fields=body.required_fields,
        sla_config=body.sla_config,
        auto_warehouse=body.auto_warehouse,
        required_documents=body.required_documents,
        is_active=body.is_active,
    )
    db.add(template)
    await db.flush()

    for idx, cl in enumerate(body.checklists):
        items_serialized = [
            x if isinstance(x, str) else x.get("title", "") for x in cl.items
        ]
        db.add(
            TemplateChecklist(
                template_id=template.id,
                checklist_id=f"cl-{idx}",
                title=cl.title,
                gate_transition=cl.gate_transition or None,
                items=items_serialized,
            )
        )
    await db.flush()
    template_for_api = await _load_template_for_api(db, template.id)
    return TemplateResponse.model_validate(template_for_api)


@router.get("/", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(
    category: str | None = Query(default=None, description="Filter by category"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[TemplateResponse]:
    """List task templates with optional filters.

    Возвращает постраничный список шаблонов задач
    с фильтрацией по категории и статусу активности.

    Аргументы:
        category: Фильтр по категории шаблона.
        is_active: Фильтр по статусу активности.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком шаблонов.
    """
    query = select(TaskTemplate).options(*_template_load_options())
    count_query = select(func.count(TaskTemplate.id))

    if category:
        query = query.where(TaskTemplate.category == category)
        count_query = count_query.where(TaskTemplate.category == category)
    if is_active is not None:
        query = query.where(TaskTemplate.is_active == is_active)
        count_query = count_query.where(TaskTemplate.is_active == is_active)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(TaskTemplate.name)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    templates = result.scalars().unique().all()

    return PaginatedResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TemplateResponse:
    """Get template detail with stages, checklists and fields.

    Возвращает полную информацию о шаблоне, включая
    стадии, чек-листы и определения кастомных полей.

    Аргументы:
        template_id: UUID шаблона.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о шаблоне.
    """
    result = await db.execute(
        select(TaskTemplate)
        .options(
            *_template_load_options(),
        )
        .where(TaskTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("TaskTemplate", str(template_id))
    return TemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TemplateResponse:
    """Update template fields.

    Частичное обновление полей шаблона задачи.

    Аргументы:
        template_id: UUID шаблона.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый шаблон.
    """
    result = await db.execute(
        select(TaskTemplate).where(TaskTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("TaskTemplate", str(template_id))

    update_data = body.model_dump(exclude_unset=True)
    checklists_data = update_data.pop("checklists", None)

    if update_data:
        await db.execute(
            update(TaskTemplate)
            .where(TaskTemplate.id == template_id)
            .values(**update_data)
        )
        await db.flush()

    if checklists_data is not None:
        await db.execute(delete(TemplateChecklist).where(TemplateChecklist.template_id == template_id))
        await db.flush()
        for idx, cl in enumerate(checklists_data):
            items_serialized = [
                x if isinstance(x, str) else x.get("title", "") for x in cl["items"]
            ]
            db.add(
                TemplateChecklist(
                    template_id=template_id,
                    checklist_id=f"cl-{idx}",
                    title=cl["title"],
                    gate_transition=cl.get("gate_transition") or None,
                    items=items_serialized,
                )
            )
        await db.flush()

    template_for_api = await _load_template_for_api(db, template_id)
    return TemplateResponse.model_validate(template_for_api)


@router.post("/{template_id}/instantiate", response_model=TaskResponse, status_code=201)
async def instantiate_template(
    template_id: uuid.UUID,
    body: InstantiateTemplate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskResponse:
    """Create a task from a template.

    Создаёт задачу на основе шаблона, копируя чек-листы
    и устанавливая начальный статус из workflow_definition.

    Аргументы:
        template_id: UUID шаблона.
        body: Параметры инстанцирования (клиент, доска, исполнитель).
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданную задачу.
    """
    result = await db.execute(
        select(TaskTemplate)
        .options(selectinload(TaskTemplate.checklists))
        .where(TaskTemplate.id == template_id, TaskTemplate.is_active.is_(True))
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("TaskTemplate", str(template_id))

    wf = template.workflow_definition or {}
    initial_status = wf.get("initial_state", "new")

    creator_id = await resolve_users_table_id(db, user)
    task = Task(
        template_id=template_id,
        board_id=body.board_id,
        client_id=body.client_id,
        deal_id=body.deal_id,
        tender_id=body.tender_id,
        assigned_to=body.assigned_to,
        created_by=creator_id,
        title=body.title or template.name,
        description=template.description,
        status=initial_status,
        priority="medium",
        custom_fields=body.custom_fields,
    )
    db.add(task)
    await db.flush()

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
    if body.observer_ids:
        await TaskService.set_observers(db, task.id, list(body.observer_ids))
        await db.flush()

    task_for_api = (
        await db.execute(
            select(Task).options(
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            ).where(Task.id == task.id)
        )
    ).scalar_one()
    return TaskResponse.model_validate(task_for_api)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a task template.

    Удаляет шаблон задачи. Существующие задачи,
    созданные из этого шаблона, не затрагиваются.

    Аргументы:
        template_id: UUID шаблона.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(
        select(TaskTemplate).where(TaskTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("TaskTemplate", str(template_id))
    await db.delete(template)
    await db.flush()
