"""Service layer for task template management.

Инкапсулирует логику работы с шаблонами задач: создание,
получение, фильтрация и инстанцирование задач из шаблонов
с автоматическим созданием чек-листов и SLA дедлайнов.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.checklist import Checklist, ChecklistItem
from app.models.task import Task
from app.models.task_status import TaskStatusHistory
from app.models.task_template import TaskTemplate, TemplateChecklist


class TemplateService:
    """Task template management service.

    Сервис управления шаблонами задач. Обеспечивает CRUD операции
    над шаблонами и инстанцирование задач из шаблонов с наследованием
    workflow, чек-листов и SLA конфигурации.
    """

    @staticmethod
    async def create_template(
        db: AsyncSession,
        data: dict[str, Any],
    ) -> TaskTemplate:
        """Create a new task template.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            data (dict[str, Any]): Данные шаблона. Обязательные ключи:
                name (str), category (str), workflow_definition (dict).
                Опциональные: description, required_fields, sla_config,
                auto_warehouse, required_documents.

        Returns:
            TaskTemplate: Созданный объект шаблона.

        Raises:
            ValidationError: Если name или workflow_definition не указаны.
        """
        if not data.get("name"):
            raise ValidationError("name", "Template name is required")
        if not data.get("workflow_definition"):
            raise ValidationError(
                "workflow_definition", "Workflow definition is required"
            )

        template = TaskTemplate(
            id=uuid.uuid4(),
            name=data["name"],
            category=data.get("category", "general"),
            description=data.get("description"),
            workflow_definition=data["workflow_definition"],
            required_fields=data.get("required_fields", []),
            sla_config=data.get("sla_config", {}),
            auto_warehouse=data.get("auto_warehouse", []),
            required_documents=data.get("required_documents", {}),
            is_active=True,
        )
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return template

    @staticmethod
    async def get_template(
        db: AsyncSession,
        template_id: uuid.UUID,
    ) -> TaskTemplate:
        """Retrieve a template by ID with eager-loaded relations.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            template_id (uuid.UUID): UUID шаблона.

        Returns:
            TaskTemplate: Найденный объект шаблона.

        Raises:
            NotFoundError: Если шаблон не найден.
        """
        stmt = (
            select(TaskTemplate)
            .options(
                joinedload(TaskTemplate.stages),
                joinedload(TaskTemplate.checklists),
                joinedload(TaskTemplate.fields),
            )
            .where(TaskTemplate.id == template_id)
        )
        result = await db.execute(stmt)
        template = result.unique().scalar_one_or_none()
        if template is None:
            raise NotFoundError("TaskTemplate", str(template_id))
        return template

    @staticmethod
    async def list_templates(
        db: AsyncSession,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[TaskTemplate]:
        """List templates with optional category filter.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            category (str | None): Фильтр по категории. Если None — все шаблоны.
            active_only (bool): Только активные шаблоны. По умолчанию True.

        Returns:
            list[TaskTemplate]: Список шаблонов, отсортированных по имени.
        """
        stmt = select(TaskTemplate)

        if active_only:
            stmt = stmt.where(TaskTemplate.is_active.is_(True))
        if category:
            stmt = stmt.where(TaskTemplate.category == category)

        stmt = stmt.order_by(TaskTemplate.name)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def instantiate_template(
        db: AsyncSession,
        template_id: uuid.UUID,
        params: dict[str, Any],
        user: dict[str, Any],
    ) -> Task:
        """Create a task from a template with checklists and SLA deadline.

        Инстанцирует задачу из шаблона: наследует workflow, создаёт чек-листы
        из TemplateChecklist, вычисляет SLA дедлайн.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            template_id (uuid.UUID): UUID шаблона для инстанцирования.
            params (dict[str, Any]): Параметры задачи:
                client_id (UUID), title (str),
                assigned_to (UUID, optional), custom_fields (dict, optional),
                priority (str, optional), due_date (datetime, optional).
            user (dict[str, Any]): Текущий пользователь с ключом "id".

        Returns:
            Task: Созданная задача со связанными чек-листами.

        Raises:
            NotFoundError: Если шаблон не найден.
            ValidationError: Если обязательные кастомные поля не заполнены.
        """
        stmt = (
            select(TaskTemplate)
            .options(
                joinedload(TaskTemplate.checklists),
                joinedload(TaskTemplate.fields),
            )
            .where(TaskTemplate.id == template_id)
        )
        result = await db.execute(stmt)
        template = result.unique().scalar_one_or_none()
        if template is None:
            raise NotFoundError("TaskTemplate", str(template_id))

        custom_fields = params.get("custom_fields", {})
        TemplateService._validate_required_fields(template, custom_fields)

        initial_status = TemplateService._get_initial_status(template)

        sla_deadline = TemplateService._calculate_sla_deadline(template)

        task = Task(
            id=uuid.uuid4(),
            template_id=template.id,
            client_id=params.get("client_id"),
            assigned_to=params.get("assigned_to"),
            created_by=user["id"],
            title=params["title"],
            status=initial_status,
            priority=params.get("priority", "medium"),
            custom_fields=custom_fields,
            due_date=params.get("due_date"),
            sla_deadline=sla_deadline,
        )
        db.add(task)

        history = TaskStatusHistory(
            id=uuid.uuid4(),
            task_id=task.id,
            from_status="",
            to_status=initial_status,
            changed_by=user["id"],
            reason="Instantiated from template",
        )
        db.add(history)

        for tmpl_cl in template.checklists:
            checklist = Checklist(
                id=uuid.uuid4(),
                task_id=task.id,
                title=tmpl_cl.title,
                gate_transition=tmpl_cl.gate_transition,
                is_completed=False,
            )
            db.add(checklist)

            for idx, item_data in enumerate(tmpl_cl.items or []):
                item_title = (
                    item_data.get("title", item_data)
                    if isinstance(item_data, dict)
                    else str(item_data)
                )
                checklist_item = ChecklistItem(
                    id=uuid.uuid4(),
                    checklist_id=checklist.id,
                    title=item_title,
                    is_completed=False,
                    order=idx,
                )
                db.add(checklist_item)

        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    def _validate_required_fields(
        template: TaskTemplate,
        custom_fields: dict[str, Any],
    ) -> None:
        """Validate that all required template fields are present.

        Args:
            template: Шаблон с определением обязательных полей.
            custom_fields: Переданные значения кастомных полей.

        Raises:
            ValidationError: Если обязательное поле отсутствует.
        """
        for field in template.fields:
            if field.is_required and field.key not in custom_fields:
                raise ValidationError(
                    field.key,
                    f"Required field '{field.label}' is missing",
                )

    @staticmethod
    def _get_initial_status(template: TaskTemplate) -> str:
        """Extract initial status from template workflow definition.

        Args:
            template: Шаблон с workflow_definition.

        Returns:
            str: Начальный статус из workflow. По умолчанию "new".
        """
        workflow = template.workflow_definition or {}
        states = workflow.get("states", [])
        return states[0] if states else "new"

    @staticmethod
    def _calculate_sla_deadline(template: TaskTemplate) -> datetime | None:
        """Calculate SLA deadline from template config.

        Args:
            template: Шаблон с sla_config.

        Returns:
            datetime | None: Дедлайн SLA или None, если не задан.
        """
        sla = template.sla_config or {}
        max_hours = sla.get("max_duration_hours")
        if max_hours:
            return datetime.now(timezone.utc) + timedelta(hours=max_hours)
        return None
