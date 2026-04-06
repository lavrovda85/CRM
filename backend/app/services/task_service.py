"""Service layer for task management operations.

Инкапсулирует доменную логику создания, получения,
обновления и удаления задач с валидацией и аудитом.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.task import Task
from app.models.task_status import TaskStatusHistory


class TaskService:
    """Task management service handling CRUD and workflow transitions.

    Сервис управления задачами. Обеспечивает создание, чтение,
    обновление и удаление задач с проверкой бизнес-правил
    и записью истории изменений статусов.
    """

    ALLOWED_UPDATE_FIELDS = frozenset({
        "title", "description", "priority", "assigned_to",
        "due_date", "custom_fields", "board_id",
    })

    @staticmethod
    async def create_task(
        db: AsyncSession,
        data: dict[str, Any],
        user: dict[str, Any],
    ) -> Task:
        """Create a new task and record initial status history.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            data (dict[str, Any]): Данные задачи. Обязательные ключи:
                title (str). Опциональные: template_id, client_id,
                assigned_to, priority, custom_fields, due_date, board_id,
                deal_id, tender_id, description.
            user (dict[str, Any]): Текущий пользователь с ключом "id" (UUID).

        Returns:
            Task: Созданный объект задачи.

        Raises:
            ValidationError: Если title не указан или пуст.
        """
        if not data.get("title"):
            raise ValidationError("title", "Title is required")

        task = Task(
            id=uuid.uuid4(),
            title=data["title"],
            description=data.get("description"),
            template_id=data.get("template_id"),
            board_id=data.get("board_id"),
            client_id=data.get("client_id"),
            deal_id=data.get("deal_id"),
            tender_id=data.get("tender_id"),
            assigned_to=data.get("assigned_to"),
            created_by=user["id"],
            status=data.get("status", "new"),
            priority=data.get("priority", "medium"),
            custom_fields=data.get("custom_fields", {}),
            due_date=data.get("due_date"),
            sla_deadline=data.get("sla_deadline"),
        )
        db.add(task)

        history = TaskStatusHistory(
            id=uuid.uuid4(),
            task_id=task.id,
            from_status="",
            to_status=task.status,
            changed_by=user["id"],
            reason="Task created",
        )
        db.add(history)

        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task:
        """Retrieve a task by ID with eager-loaded relations.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID): UUID задачи.

        Returns:
            Task: Найденный объект задачи.

        Raises:
            NotFoundError: Если задача не найдена.
        """
        stmt = (
            select(Task)
            .options(
                joinedload(Task.template),
                joinedload(Task.client),
                joinedload(Task.assignee),
                joinedload(Task.checklists),
            )
            .where(Task.id == task_id)
        )
        result = await db.execute(stmt)
        task = result.unique().scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))
        return task

    @staticmethod
    async def list_tasks(
        db: AsyncSession,
        filters: dict[str, Any],
    ) -> list[Task]:
        """List tasks with optional filtering.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            filters (dict[str, Any]): Фильтры. Допустимые ключи:
                status (str), assigned_to (UUID), client_id (UUID),
                board_id (UUID), priority (str), limit (int), offset (int).

        Returns:
            list[Task]: Список задач, отсортированных по дате создания (desc).
        """
        stmt = select(Task)

        if status := filters.get("status"):
            stmt = stmt.where(Task.status == status)
        if assigned_to := filters.get("assigned_to"):
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if client_id := filters.get("client_id"):
            stmt = stmt.where(Task.client_id == client_id)
        if board_id := filters.get("board_id"):
            stmt = stmt.where(Task.board_id == board_id)
        if priority := filters.get("priority"):
            stmt = stmt.where(Task.priority == priority)

        limit = min(filters.get("limit", 50), 200)
        offset = filters.get("offset", 0)

        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        data: dict[str, Any],
        user: dict[str, Any],
    ) -> Task:
        """Update allowed fields of an existing task.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID): UUID задачи для обновления.
            data (dict[str, Any]): Словарь обновляемых полей.
                Допустимые: title, description, priority, assigned_to,
                due_date, custom_fields, board_id.
            user (dict[str, Any]): Текущий пользователь с ключом "id".

        Returns:
            Task: Обновлённый объект задачи.

        Raises:
            NotFoundError: Если задача не найдена.
            ValidationError: Если переданы недопустимые поля.
        """
        invalid_keys = set(data.keys()) - TaskService.ALLOWED_UPDATE_FIELDS
        if invalid_keys:
            raise ValidationError(
                ", ".join(invalid_keys),
                "Fields not allowed for update via this method",
            )

        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))

        for key, value in data.items():
            setattr(task, key, value)

        task.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        user: dict[str, Any],
    ) -> None:
        """Soft-delete or hard-delete a task by ID.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID): UUID задачи для удаления.
            user (dict[str, Any]): Текущий пользователь с ключом "id".

        Raises:
            NotFoundError: Если задача не найдена.
        """
        stmt = select(Task).where(Task.id == task_id)
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))

        await db.delete(task)
        await db.flush()
