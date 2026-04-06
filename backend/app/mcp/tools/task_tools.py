"""MCP tools for task management in HVAC CRM/ERP.

Инструменты для создания, обновления, перехода статусов,
получения списка и деталей задач через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def create_task(
    title: str,
    template_id: str | None = None,
    client_id: str | None = None,
    assigned_to: str | None = None,
    custom_fields: dict | None = None,
    priority: str = "medium",
    due_date: str | None = None,
) -> dict:
    """Create a new task in the HVAC CRM/ERP system.

    Создаёт новую задачу, опционально из шаблона. Если указан template_id,
    задача наследует workflow, чек-листы и обязательные поля из шаблона.

    Args:
        title (str): Заголовок задачи. Обязательный.
        template_id (str | None): UUID шаблона задачи. Если указан — задача
            создаётся из шаблона с наследованием workflow и чек-листов.
        client_id (str | None): UUID клиента, к которому привязана задача.
        assigned_to (str | None): UUID исполнителя задачи.
        custom_fields (dict | None): Словарь кастомных полей {key: value}.
        priority (str): Приоритет задачи: "low", "medium", "high", "critical".
            По умолчанию "medium".
        due_date (str | None): Крайний срок в формате ISO 8601
            (например, "2026-04-15T18:00:00Z").

    Returns:
        dict: Созданная задача с полями id, title, status, priority,
            assigned_to, template_id, client_id, custom_fields,
            due_date, created_at.

    Example:
        AI agent: "Создай задачу на монтаж кондиционера для клиента"
        >>> create_task(
        ...     title="Монтаж кондиционера Daikin FTXB35C",
        ...     template_id="a1b2c3d4-...",
        ...     client_id="e5f6a7b8-...",
        ...     assigned_to="c9d0e1f2-...",
        ...     priority="high",
        ...     due_date="2026-04-15T18:00:00Z",
        ... )
    """
    # TODO: Validate template_id exists via TaskTemplate query
    # TODO: Validate client_id exists via Client query
    # TODO: Validate assigned_to exists via User query
    # TODO: Create Task row with inherited workflow from template
    # TODO: Create Checklist rows from TemplateChecklist if template_id given
    # TODO: Record TaskStatusHistory entry for initial status
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": task_id,
        "title": title,
        "status": "new",
        "priority": priority,
        "template_id": template_id,
        "client_id": client_id,
        "assigned_to": assigned_to,
        "custom_fields": custom_fields or {},
        "due_date": due_date,
        "created_at": now,
    }


@mcp.tool()
async def update_task(task_id: str, fields: dict) -> dict:
    """Update fields of an existing task.

    Обновляет одно или несколько полей существующей задачи.
    Нельзя менять статус через этот инструмент — используйте transition_task.

    Args:
        task_id (str): UUID задачи для обновления.
        fields (dict): Словарь полей для обновления. Допустимые ключи:
            title, description, priority, assigned_to, due_date, custom_fields.

    Returns:
        dict: Обновлённая задача с полями id, title, status, priority,
            assigned_to, custom_fields, due_date, updated_at.

    Example:
        AI agent: "Измени приоритет задачи на критический и назначь нового исполнителя"
        >>> update_task(
        ...     task_id="a1b2c3d4-...",
        ...     fields={"priority": "critical", "assigned_to": "new-user-uuid"},
        ... )
    """
    # TODO: SELECT task by task_id, raise NotFoundError if absent
    # TODO: Validate fields keys against allowed set
    # TODO: UPDATE task SET ... WHERE id = task_id
    # TODO: Return refreshed task row
    now = datetime.utcnow().isoformat()
    return {
        "id": task_id,
        "updated_fields": list(fields.keys()),
        "updated_at": now,
        **fields,
    }


@mcp.tool()
async def transition_task(
    task_id: str,
    to_status: str,
    reason: str = "",
) -> dict:
    """Transition a task to a new workflow status.

    Выполняет переход задачи в новый статус согласно workflow_definition
    шаблона. Проверяет допустимость перехода и заполненность gate-чеклистов.

    Args:
        task_id (str): UUID задачи.
        to_status (str): Целевой статус (например, "in_progress", "review",
            "completed"). Должен быть допустимым переходом из текущего статуса.
        reason (str): Причина перехода (для аудита). По умолчанию пустая строка.

    Returns:
        dict: Результат перехода с полями id, from_status, to_status,
            transitioned_at, reason.

    Example:
        AI agent: "Переведи задачу в статус 'выполнена'"
        >>> transition_task(
        ...     task_id="a1b2c3d4-...",
        ...     to_status="completed",
        ...     reason="Все работы выполнены, акт подписан",
        ... )
    """
    # TODO: SELECT task by task_id with template.workflow_definition
    # TODO: Validate to_status is reachable from current status
    # TODO: Check gate checklists are completed for this transition
    # TODO: UPDATE task.status, set started_at/completed_at if applicable
    # TODO: INSERT TaskStatusHistory record
    now = datetime.utcnow().isoformat()
    return {
        "id": task_id,
        "from_status": "current_status_placeholder",
        "to_status": to_status,
        "transitioned_at": now,
        "reason": reason,
    }


@mcp.tool()
async def list_tasks(
    status: str | None = None,
    assigned_to: str | None = None,
    client_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tasks with optional filters.

    Возвращает список задач с возможностью фильтрации по статусу,
    исполнителю и клиенту. Результаты отсортированы по дате создания (desc).

    Args:
        status (str | None): Фильтр по статусу задачи
            (например, "new", "in_progress", "completed").
        assigned_to (str | None): UUID исполнителя для фильтрации.
        client_id (str | None): UUID клиента для фильтрации.
        limit (int): Максимальное количество задач. По умолчанию 50, макс. 200.

    Returns:
        list[dict]: Список задач, каждая содержит id, title, status,
            priority, assigned_to, client_id, due_date, created_at.

    Example:
        AI agent: "Покажи все незавершённые задачи монтажника Иванова"
        >>> list_tasks(
        ...     status="in_progress",
        ...     assigned_to="user-uuid-ivanov",
        ...     limit=20,
        ... )
    """
    # TODO: Build SELECT query with optional WHERE clauses
    # TODO: Apply ORDER BY created_at DESC, LIMIT min(limit, 200)
    # TODO: Return list of task dicts
    clamped_limit = min(limit, 200)
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "Placeholder task",
            "status": status or "new",
            "priority": "medium",
            "assigned_to": assigned_to,
            "client_id": client_id,
            "due_date": None,
            "created_at": datetime.utcnow().isoformat(),
            "_limit": clamped_limit,
        }
    ]


@mcp.tool()
async def get_task_detail(task_id: str) -> dict:
    """Get full details of a specific task including relations.

    Возвращает полную информацию о задаче, включая связанные данные:
    клиент, исполнитель, шаблон, чек-листы, документы и историю статусов.

    Args:
        task_id (str): UUID задачи.

    Returns:
        dict: Полные данные задачи с вложенными объектами:
            id, title, description, status, priority, due_date,
            template (id, name), client (id, name), assignee (id, name),
            checklists (list), documents (list), status_history (list),
            custom_fields, created_at, updated_at.

    Example:
        AI agent: "Покажи полную информацию по задаче монтажа"
        >>> get_task_detail(task_id="a1b2c3d4-...")
    """
    # TODO: SELECT task with joinedload(template, client, assignee)
    # TODO: SELECT checklists with items for this task
    # TODO: SELECT documents for this task
    # TODO: SELECT status_history for this task
    # TODO: Raise NotFoundError if task not found
    now = datetime.utcnow().isoformat()
    return {
        "id": task_id,
        "title": "Placeholder task",
        "description": None,
        "status": "new",
        "priority": "medium",
        "due_date": None,
        "template": None,
        "client": None,
        "assignee": None,
        "checklists": [],
        "documents": [],
        "status_history": [],
        "custom_fields": {},
        "created_at": now,
        "updated_at": now,
    }
