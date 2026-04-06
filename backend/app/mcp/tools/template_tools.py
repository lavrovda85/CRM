"""MCP tools for task template management in HVAC CRM/ERP.

Инструменты для просмотра, создания шаблонов задач
и инстанцирования задач из шаблонов через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def list_templates(category: str | None = None) -> list[dict]:
    """List available task templates, optionally filtered by category.

    Возвращает список активных шаблонов задач. Используйте для выбора
    подходящего шаблона перед созданием задачи.

    Args:
        category (str | None): Фильтр по категории шаблона:
            "installation", "maintenance", "repair", "inspection", "general".
            Если не указан — возвращаются все активные шаблоны.

    Returns:
        list[dict]: Список шаблонов, каждый содержит id, name, category,
            description, required_fields, sla_config, is_active.

    Example:
        AI agent: "Какие шаблоны есть для монтажных работ?"
        >>> list_templates(category="installation")
    """
    # TODO: SELECT * FROM task_templates WHERE is_active = true
    # TODO: Apply category filter if provided
    # TODO: JOIN template_fields, template_stages for summary
    return [
        {
            "id": str(uuid.uuid4()),
            "name": "Placeholder template",
            "category": category or "general",
            "description": None,
            "required_fields": [],
            "sla_config": {},
            "is_active": True,
        }
    ]


@mcp.tool()
async def create_template(
    name: str,
    category: str,
    workflow_definition: dict,
    required_fields: list[dict] | None = None,
    sla_config: dict | None = None,
) -> dict:
    """Create a new task template with workflow and field definitions.

    Создаёт новый шаблон задачи с определением конечного автомата (workflow),
    обязательных полей и SLA конфигурации.

    Args:
        name (str): Название шаблона (например, "Монтаж сплит-системы").
        category (str): Категория шаблона: "installation", "maintenance",
            "repair", "inspection", "general".
        workflow_definition (dict): Определение конечного автомата в формате:
            {"states": ["new", "in_progress", ...],
             "transitions": [{"from": "new", "to": "in_progress"}, ...]}.
        required_fields (list[dict] | None): Список определений полей,
            каждое: {"key": "area_sqm", "label": "Площадь", "field_type": "decimal",
            "is_required": true}.
        sla_config (dict | None): Конфигурация SLA:
            {"max_duration_hours": 48, "warning_at_percent": 75}.

    Returns:
        dict: Созданный шаблон с полями id, name, category,
            workflow_definition, required_fields, sla_config, created_at.

    Example:
        AI agent: "Создай шаблон для техобслуживания кондиционеров"
        >>> create_template(
        ...     name="ТО кондиционера",
        ...     category="maintenance",
        ...     workflow_definition={
        ...         "states": ["new", "scheduled", "in_progress", "completed"],
        ...         "transitions": [
        ...             {"from": "new", "to": "scheduled"},
        ...             {"from": "scheduled", "to": "in_progress"},
        ...             {"from": "in_progress", "to": "completed"},
        ...         ],
        ...     },
        ...     sla_config={"max_duration_hours": 24, "warning_at_percent": 75},
        ... )
    """
    # TODO: INSERT INTO task_templates (name, category, workflow_definition, ...)
    # TODO: INSERT INTO template_fields for each required_fields entry
    # TODO: Validate workflow_definition structure (states + transitions)
    template_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": template_id,
        "name": name,
        "category": category,
        "workflow_definition": workflow_definition,
        "required_fields": required_fields or [],
        "sla_config": sla_config or {},
        "is_active": True,
        "created_at": now,
    }


@mcp.tool()
async def instantiate_template(
    template_id: str,
    client_id: str,
    title: str,
    assigned_to: str | None = None,
    custom_fields: dict | None = None,
) -> dict:
    """Create a task from a template, inheriting workflow and checklists.

    Инстанцирует задачу из шаблона: копирует workflow, создаёт чек-листы
    из TemplateChecklist, применяет SLA дедлайны и обязательные поля.

    Args:
        template_id (str): UUID шаблона задачи для инстанцирования.
        client_id (str): UUID клиента, к которому привязывается задача.
        title (str): Заголовок задачи (может отличаться от шаблона).
        assigned_to (str | None): UUID исполнителя.
        custom_fields (dict | None): Значения кастомных полей шаблона
            (например, {"area_sqm": 45, "equipment_model": "Daikin FTXB35C"}).

    Returns:
        dict: Созданная задача с полями id, title, status, template_id,
            client_id, assigned_to, checklists_created, sla_deadline, created_at.

    Example:
        AI agent: "Создай задачу на монтаж из шаблона для клиента Петрова"
        >>> instantiate_template(
        ...     template_id="tmpl-uuid-...",
        ...     client_id="client-uuid-...",
        ...     title="Монтаж кондиционера — кв. Петрова",
        ...     assigned_to="user-uuid-...",
        ...     custom_fields={"area_sqm": 45, "floor": 7},
        ... )
    """
    # TODO: SELECT template with checklists, fields, stages
    # TODO: Validate required custom_fields against template.required_fields
    # TODO: INSERT task with status = first state from workflow_definition
    # TODO: Calculate sla_deadline from sla_config.max_duration_hours
    # TODO: INSERT checklists from template_checklists with items
    # TODO: INSERT checklist_items from template_checklists.items JSON
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": task_id,
        "title": title,
        "status": "new",
        "template_id": template_id,
        "client_id": client_id,
        "assigned_to": assigned_to,
        "custom_fields": custom_fields or {},
        "checklists_created": 0,
        "sla_deadline": None,
        "created_at": now,
    }
