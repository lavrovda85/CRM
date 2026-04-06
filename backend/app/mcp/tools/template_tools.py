"""MCP tools for task template management in SPEC CRM/ERP.

Инструменты для просмотра, создания шаблонов задач
и инстанцирования задач из шаблонов через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.mcp.server import mcp
from app.mcp.actor_context import actor_dict_for_service
from app.core.database import async_session_factory
from app.models.task_template import TemplateChecklist
from app.schemas.template import TemplateResponse
from app.services.template_service import TemplateService


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
    async with async_session_factory() as db:
        templates = await TemplateService.list_templates(db, category=category, active_only=True)
        # Возвращаем компактный список (без стадий/полей) — MCP-агенту обычно хватает.
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "required_fields": t.required_fields or [],
                "sla_config": t.sla_config or {},
                "is_active": bool(t.is_active),
            }
            for t in templates
        ]


@mcp.tool()
async def create_template(
    name: str,
    category: str,
    workflow_definition: dict,
    required_fields: list[dict] | None = None,
    sla_config: dict | None = None,
    checklists: list[dict] | None = None,
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
    data: dict[str, Any] = {
        "name": name,
        "category": category,
        "workflow_definition": workflow_definition,
        "required_fields": required_fields or [],
        "sla_config": sla_config or {},
    }

    async with async_session_factory() as db:
        tpl = await TemplateService.create_template(db, data)

        # Чек-листы храним как TemplateChecklist (через DB), т.к. service-layer
        # пока не включает CRUD чек-листов шаблона.
        checklists = checklists or []
        for idx, cl in enumerate(checklists):
            items_raw = cl.get("items") or []
            items_serialized = [
                x if isinstance(x, str) else x.get("title", "") for x in items_raw
            ]
            db.add(
                TemplateChecklist(
                    template_id=tpl.id,
                    checklist_id=cl.get("checklist_id") or f"cl-{idx}",
                    title=cl.get("title") or f"Чек-лист {idx + 1}",
                    gate_transition=cl.get("gate_transition") or None,
                    items=items_serialized,
                )
            )
        await db.flush()
        await db.commit()

        full = await TemplateService.get_template(db, tpl.id)
        return TemplateResponse.model_validate(full).model_dump(mode="json")


@mcp.tool()
async def get_template(template_id: str) -> dict:
    """Get a task template by ID, including checklists, stages and fields.

    Аргументы:
        template_id: UUID шаблона.

    Возвращает:
        Полный TemplateResponse.
    """
    async with async_session_factory() as db:
        tpl = await TemplateService.get_template(db, uuid.UUID(template_id))
        return TemplateResponse.model_validate(tpl).model_dump(mode="json")


@mcp.tool()
async def update_template(template_id: str, fields: dict) -> dict:
    """Update a task template by ID.

    Поддерживает обновление основных полей и замену чек-листов, если
    передано `checklists` (полностью заменяет текущие).

    Аргументы:
        template_id: UUID шаблона.
        fields: Поля для обновления. Опционально включает `checklists`.
    """
    tid = uuid.UUID(template_id)
    async with async_session_factory() as db:
        tpl = await TemplateService.get_template(db, tid)

        # простое setattr для известных полей
        for key in (
            "name",
            "category",
            "description",
            "workflow_definition",
            "required_fields",
            "sla_config",
            "auto_warehouse",
            "required_documents",
            "is_active",
        ):
            if key in fields:
                setattr(tpl, key, fields[key])

        if "checklists" in fields:
            new_checklists = fields.get("checklists") or []
            # replace all
            from sqlalchemy import delete as sa_delete

            await db.execute(sa_delete(TemplateChecklist).where(TemplateChecklist.template_id == tid))
            await db.flush()
            for idx, cl in enumerate(new_checklists):
                items_raw = cl.get("items") or []
                items_serialized = [
                    x if isinstance(x, str) else x.get("title", "") for x in items_raw
                ]
                db.add(
                    TemplateChecklist(
                        template_id=tid,
                        checklist_id=cl.get("checklist_id") or f"cl-{idx}",
                        title=cl.get("title") or f"Чек-лист {idx + 1}",
                        gate_transition=cl.get("gate_transition") or None,
                        items=items_serialized,
                    )
                )
            await db.flush()

        await db.flush()
        await db.commit()

        full = await TemplateService.get_template(db, tid)
        return TemplateResponse.model_validate(full).model_dump(mode="json")


@mcp.tool()
async def delete_template(template_id: str) -> dict:
    """Delete a task template by ID (hard delete)."""
    tid = uuid.UUID(template_id)
    async with async_session_factory() as db:
        tpl = await TemplateService.get_template(db, tid)
        await db.delete(tpl)
        await db.flush()
        await db.commit()
        return {"deleted": True, "id": template_id}


@mcp.tool()
async def instantiate_template(
    template_id: str,
    title: str,
    client_id: str | None = None,
    assigned_to: str | None = None,
    custom_fields: dict | None = None,
    due_date: str | None = None,
    priority: str = "medium",
) -> dict:
    """Create a task from a template, inheriting workflow and checklists.

    Инстанцирует задачу из шаблона: копирует workflow, создаёт чек-листы
    из TemplateChecklist, применяет SLA дедлайны и обязательные поля.

    Args:
        template_id (str): UUID шаблона задачи для инстанцирования.
        title (str): Заголовок задачи (может отличаться от шаблона).
        client_id (str | None): UUID клиента (опционально для задач без привязки к карточке клиента).
        assigned_to (str | None): UUID исполнителя.
        custom_fields (dict | None): Значения кастомных полей шаблона
            (например, {"area_sqm": 45, "equipment_model": "Daikin FTXB35C"}).
        due_date (str | None): ISO 8601 срок выполнения.
        priority (str): low | medium | high | critical.

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
    tid = uuid.UUID(template_id)
    params: dict[str, Any] = {
        "client_id": uuid.UUID(client_id) if client_id else None,
        "title": title,
        "assigned_to": uuid.UUID(assigned_to) if assigned_to else None,
        "custom_fields": custom_fields or {},
        "priority": priority,
    }
    if due_date:
        params["due_date"] = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

    actor = actor_dict_for_service()

    async with async_session_factory() as db:
        task = await TemplateService.instantiate_template(db, tid, params, actor)
        await db.commit()
        # Возвращаем краткое представление (для MCP достаточно).
        return {
            "id": str(task.id),
            "title": task.title,
            "status": task.status,
            "template_id": str(task.template_id) if task.template_id else None,
            "client_id": str(task.client_id) if task.client_id else None,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            "custom_fields": task.custom_fields or {},
            "sla_deadline": task.sla_deadline.isoformat() if task.sla_deadline else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        }
