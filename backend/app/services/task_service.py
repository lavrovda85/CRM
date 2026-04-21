"""Service layer for task management operations.

Инкапсулирует доменную логику создания, получения,
обновления и удаления задач с валидацией и аудитом.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Text, and_, cast, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.task import (
    ALLOWED_TASK_VISIBILITIES,
    TASK_VISIBILITY_COMPANY,
    TASK_VISIBILITY_PARTICIPANTS,
    Task,
    task_co_assignees,
    task_observers,
)
from app.models.task_status import TaskStatusHistory

_CO_ASSIGNEES_UNSET = object()
_OBSERVER_IDS_UNSET = object()


class TaskService:
    """Task management service handling CRUD and workflow transitions.

    Сервис управления задачами. Обеспечивает создание, чтение,
    обновление и удаление задач с проверкой бизнес-правил
    и записью истории изменений статусов.
    """

    ALLOWED_UPDATE_FIELDS = frozenset({
        "title", "description", "priority", "assigned_to",
        "due_date", "started_at", "completed_at", "sla_deadline",
        "custom_fields", "board_id", "requested_by",
        "observer_ids",
        "visibility",
    })

    @staticmethod
    def _co_assignee_exists_clause(viewer_id: uuid.UUID):
        """EXISTS: ``viewer_id`` is a co-assignee on ``Task``."""
        return (
            select(1)
            .select_from(task_co_assignees)
            .where(
                task_co_assignees.c.task_id == Task.id,
                task_co_assignees.c.user_id == viewer_id,
            )
            .exists()
        )

    @staticmethod
    def _observer_exists_clause(viewer_id: uuid.UUID):
        """EXISTS: ``viewer_id`` is an observer on ``Task``."""
        return (
            select(1)
            .select_from(task_observers)
            .where(
                task_observers.c.task_id == Task.id,
                task_observers.c.user_id == viewer_id,
            )
            .exists()
        )

    @staticmethod
    def _participant_access_clause(viewer_id: uuid.UUID):
        """SQL OR: user is creator, requester, assignee, co-assignee, or observer."""
        co_exists = TaskService._co_assignee_exists_clause(viewer_id)
        obs_exists = TaskService._observer_exists_clause(viewer_id)
        return or_(
            Task.created_by == viewer_id,
            Task.requested_by == viewer_id,
            Task.assigned_to == viewer_id,
            co_exists,
            obs_exists,
        )

    @staticmethod
    def sql_client_portal_task_scope(viewer_id: uuid.UUID):
        """Tasks visible to external ``client`` users only (no company-wide bypass).

        Includes creator, primary assignee, co-assignee, and observer — not requester-only.
        """
        return or_(
            Task.created_by == viewer_id,
            Task.assigned_to == viewer_id,
            TaskService._co_assignee_exists_clause(viewer_id),
            TaskService._observer_exists_clause(viewer_id),
        )

    @staticmethod
    def sql_tasks_row_visible(viewer_id: uuid.UUID, *, client_portal_only: bool):
        """SQL predicate for one task row: staff visibility rules or strict client scope."""
        if client_portal_only:
            return TaskService.sql_client_portal_task_scope(viewer_id)
        return TaskService.sql_task_visible_to_user(viewer_id)

    @staticmethod
    def sql_task_visible_to_user(viewer_id: uuid.UUID):
        """Restrict rows to tasks the viewer may see (company-wide vs participants-only)."""
        pc = TaskService._participant_access_clause(viewer_id)
        return or_(
            Task.visibility == TASK_VISIBILITY_COMPANY,
            Task.visibility.is_(None),
            and_(Task.visibility == TASK_VISIBILITY_PARTICIPANTS, pc),
        )

    @staticmethod
    def user_can_view_task(
        task: Task,
        viewer_id: uuid.UUID,
        *,
        client_portal_only: bool = False,
    ) -> bool:
        """Return True if ``viewer_id`` may see this task (ORM row, relations optional).

        Args:
            task: Loaded task (co_assignees / observers optional).
            viewer_id: CRM ``users.id`` of the viewer.
            client_portal_only: If True, ignore company-wide visibility — only creator,
                assignee, co-assignee, or observer.
        """
        if client_portal_only:
            if task.created_by == viewer_id or task.assigned_to == viewer_id:
                return True
            co = getattr(task, "co_assignees", None) or []
            obs = getattr(task, "observers", None) or []
            return any(u.id == viewer_id for u in co) or any(u.id == viewer_id for u in obs)

        vis = task.visibility or TASK_VISIBILITY_COMPANY
        if vis != TASK_VISIBILITY_PARTICIPANTS:
            return True
        if task.created_by == viewer_id or task.requested_by == viewer_id or task.assigned_to == viewer_id:
            return True
        co = getattr(task, "co_assignees", None) or []
        obs = getattr(task, "observers", None) or []
        if any(u.id == viewer_id for u in co):
            return True
        if any(u.id == viewer_id for u in obs):
            return True
        return False

    @staticmethod
    async def set_co_assignees(
        db: AsyncSession,
        task_id: uuid.UUID,
        user_ids: list[uuid.UUID],
    ) -> None:
        """Replace task co-assignees with ``user_ids`` (deduplicated, order preserved)."""
        await db.execute(delete(task_co_assignees).where(task_co_assignees.c.task_id == task_id))
        seen: set[uuid.UUID] = set()
        for uid in user_ids:
            if uid in seen:
                continue
            seen.add(uid)
            await db.execute(
                insert(task_co_assignees).values(task_id=task_id, user_id=uid),
            )

    @staticmethod
    async def set_observers(
        db: AsyncSession,
        task_id: uuid.UUID,
        user_ids: list[uuid.UUID],
    ) -> None:
        """Replace task observers with ``user_ids`` (deduplicated, order preserved)."""
        await db.execute(delete(task_observers).where(task_observers.c.task_id == task_id))
        seen: set[uuid.UUID] = set()
        for uid in user_ids:
            if uid in seen:
                continue
            seen.add(uid)
            await db.execute(
                insert(task_observers).values(task_id=task_id, user_id=uid),
            )

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
                deal_id, tender_id, description, requested_by, co_assignee_ids (list[UUID]).
            user (dict[str, Any]): Текущий пользователь с ключом "id" (UUID).

        Returns:
            Task: Созданный объект задачи.

        Raises:
            ValidationError: Если title не указан или пуст.
        """
        if not data.get("title"):
            raise ValidationError("title", "Title is required")

        co_raw = data.get("co_assignee_ids") or []
        obs_raw = data.get("observer_ids") or []
        vis = data.get("visibility", TASK_VISIBILITY_PARTICIPANTS)
        if vis not in ALLOWED_TASK_VISIBILITIES:
            raise ValidationError("visibility", "Invalid visibility value")

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
            requested_by=data.get("requested_by"),
            status=data.get("status", "new"),
            priority=data.get("priority", "medium"),
            custom_fields=data.get("custom_fields", {}),
            due_date=data.get("due_date"),
            sla_deadline=data.get("sla_deadline"),
            visibility=vis,
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
        if co_raw:
            uids = [uuid.UUID(str(x)) for x in co_raw]
            await TaskService.set_co_assignees(db, task.id, uids)
        if obs_raw:
            uids = [uuid.UUID(str(x)) for x in obs_raw]
            await TaskService.set_observers(db, task.id, uids)
        await db.refresh(task)
        return task

    @staticmethod
    async def get_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        *,
        only_active: bool = True,
        viewer_user_id: uuid.UUID | None = None,
        client_portal_only: bool = False,
    ) -> Task:
        """Retrieve a task by ID with eager-loaded relations.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID): UUID задачи.
            only_active (bool): If True, exclude soft-deleted tasks (default).
            viewer_user_id: If set, enforce task visibility for this user.
            client_portal_only: If True with ``viewer_user_id``, use strict client scope.

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
                joinedload(Task.creator),
                joinedload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
                joinedload(Task.checklists),
            )
            .where(Task.id == task_id)
        )
        if only_active:
            stmt = stmt.where(Task.active_filter())
        if viewer_user_id is not None:
            stmt = stmt.where(
                TaskService.sql_tasks_row_visible(
                    viewer_user_id,
                    client_portal_only=client_portal_only,
                )
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
                board_id (UUID), priority (str), limit (int), offset (int),
                involves_user (UUID): primary assignee OR co-assignee.
                viewer_user_id (UUID): Enforce visibility for this user (recommended for API).
                client_portal_only (bool): If True, use strict client scope with ``viewer_user_id``.

        Returns:
            list[Task]: Список задач, отсортированных по дате создания (desc).
        """
        stmt = (
            select(Task)
            .options(
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            )
            .where(Task.active_filter())
        )

        if vu := filters.get("viewer_user_id"):
            vuid = vu if isinstance(vu, uuid.UUID) else uuid.UUID(str(vu))
            cp = bool(filters.get("client_portal_only"))
            stmt = stmt.where(TaskService.sql_tasks_row_visible(vuid, client_portal_only=cp))

        if status := filters.get("status"):
            stmt = stmt.where(Task.status == status)
        if involves := filters.get("involves_user"):
            iuid = involves if isinstance(involves, uuid.UUID) else uuid.UUID(str(involves))
            co_exists = TaskService._co_assignee_exists_clause(iuid)
            obs_exists = TaskService._observer_exists_clause(iuid)
            stmt = stmt.where(or_(Task.assigned_to == iuid, co_exists, obs_exists))
        elif assigned_to := filters.get("assigned_to"):
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if client_id := filters.get("client_id"):
            stmt = stmt.where(Task.client_id == client_id)
        if board_id := filters.get("board_id"):
            stmt = stmt.where(Task.board_id == board_id)
        if priority := filters.get("priority"):
            stmt = stmt.where(Task.priority == priority)

        def _as_limit(raw: Any, default: int, cap: int) -> int:
            try:
                n = int(raw)
            except (TypeError, ValueError):
                n = default
            return max(1, min(n, cap))

        def _as_offset(raw: Any) -> int:
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                return 0

        limit = _as_limit(filters.get("limit", 50), 50, 200)
        offset = _as_offset(filters.get("offset", 0))

        stmt = stmt.order_by(Task.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _escape_like_literal(term: str) -> str:
        """Escape ``%`` and ``_`` for SQL ``LIKE``/``ILIKE`` with escape character ``\\\\``."""
        return (
            term.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

    @staticmethod
    async def search_tasks(
        db: AsyncSession,
        *,
        q: str,
        limit: int = 25,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        involves_user: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        viewer_user_id: uuid.UUID | None = None,
        client_portal_only: bool = False,
    ) -> list[Task]:
        """Search tasks by substring in title, description, or JSON ``custom_fields`` (ILIKE).

        Args:
            db: DB session.
            q: Search text (min 2 non-space chars after strip).
            limit: Max rows (capped 1–100).
            status: Optional status filter.
            assigned_to: Optional primary assignee filter.
            involves_user: Optional filter — primary assignee OR co-assignee.
            client_id: Optional client filter.
            viewer_user_id: If set, enforce task visibility for this user.
            client_portal_only: If True with ``viewer_user_id``, use strict client scope.

        Returns:
            Matching tasks, newest first.

        Raises:
            ValidationError: If ``q`` is too short.
        """
        raw = (q or "").strip()
        if len(raw) < 2:
            raise ValidationError("q", "Search text must be at least 2 characters")

        esc = TaskService._escape_like_literal(raw)
        pattern = f"%{esc}%"

        stmt = (
            select(Task)
            .options(
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            )
            .where(Task.active_filter())
            .where(
                or_(
                    Task.title.ilike(pattern, escape="\\"),
                    Task.description.ilike(pattern, escape="\\"),
                    cast(Task.custom_fields, Text).ilike(pattern, escape="\\"),
                )
            )
        )
        if viewer_user_id is not None:
            stmt = stmt.where(
                TaskService.sql_tasks_row_visible(
                    viewer_user_id,
                    client_portal_only=client_portal_only,
                )
            )
        if status:
            stmt = stmt.where(Task.status == status)
        if involves_user is not None:
            iuid = involves_user
            co_exists = TaskService._co_assignee_exists_clause(iuid)
            obs_exists = TaskService._observer_exists_clause(iuid)
            stmt = stmt.where(or_(Task.assigned_to == iuid, co_exists, obs_exists))
        elif assigned_to is not None:
            stmt = stmt.where(Task.assigned_to == assigned_to)
        if client_id is not None:
            stmt = stmt.where(Task.client_id == client_id)

        try:
            lim = int(limit)
        except (TypeError, ValueError):
            lim = 25
        lim = max(1, min(lim, 100))

        stmt = stmt.order_by(Task.created_at.desc()).limit(lim)
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
                due_date, started_at, completed_at, sla_deadline,
                custom_fields, board_id, requested_by.
                co_assignee_ids: full replacement list when key is present.
                observer_ids: full replacement list when key is present.
            user (dict[str, Any]): Текущий пользователь с ключом "id".

        Returns:
            Task: Обновлённый объект задачи.

        Raises:
            NotFoundError: Если задача не найдена.
            ValidationError: Если переданы недопустимые поля.
        """
        raw = dict(data)
        co_ids_raw = raw.pop("co_assignee_ids", _CO_ASSIGNEES_UNSET)
        obs_ids_raw = raw.pop("observer_ids", _OBSERVER_IDS_UNSET)

        invalid_keys = set(raw.keys()) - TaskService.ALLOWED_UPDATE_FIELDS
        if invalid_keys:
            raise ValidationError(
                ", ".join(invalid_keys),
                "Fields not allowed for update via this method",
            )

        if "visibility" in raw and raw["visibility"] not in ALLOWED_TASK_VISIBILITIES:
            raise ValidationError("visibility", "Invalid visibility value")

        stmt = select(Task).where(Task.id == task_id, Task.active_filter())
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))

        for key, value in raw.items():
            setattr(task, key, value)

        task.updated_at = datetime.now(timezone.utc)
        await db.flush()
        if co_ids_raw is not _CO_ASSIGNEES_UNSET:
            uids = [uuid.UUID(str(x)) for x in (co_ids_raw or [])]
            await TaskService.set_co_assignees(db, task_id, uids)
        if obs_ids_raw is not _OBSERVER_IDS_UNSET:
            uids = [uuid.UUID(str(x)) for x in (obs_ids_raw or [])]
            await TaskService.set_observers(db, task_id, uids)
        await db.refresh(task)
        return task

    @staticmethod
    async def delete_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        user: dict[str, Any],
    ) -> None:
        """Soft-delete a task: set ``deleted_at`` / ``deleted_by``; keep history and relations.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID): UUID задачи для удаления.
            user (dict[str, Any]): Текущий пользователь с ключом "id".

        Raises:
            NotFoundError: Если активная задача не найдена (уже удалена или нет строки).
        """
        stmt = select(Task).where(Task.id == task_id, Task.active_filter())
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))

        task.deleted_at = datetime.now(timezone.utc)
        task.deleted_by = user["id"]
        await db.flush()

    @staticmethod
    async def restore_task(
        db: AsyncSession,
        task_id: uuid.UUID,
        user: dict[str, Any],
    ) -> Task:
        """Clear soft-delete flags so the task is visible again in normal lists.

        Args:
            db: DB session.
            task_id: Task to restore.
            user: Current user (``id`` used for audit if extended later).

        Returns:
            Restored task row.

        Raises:
            NotFoundError: If no soft-deleted task exists for ``task_id``.
        """
        _ = user
        stmt = select(Task).where(Task.id == task_id, Task.deleted_at.is_not(None))
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise NotFoundError("Task", str(task_id))

        task.deleted_at = None
        task.deleted_by = None
        await db.flush()
        await db.refresh(task)
        return task

    @staticmethod
    async def list_deleted_tasks(
        db: AsyncSession,
        *,
        company_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[Task], int]:
        """List soft-deleted tasks (newest deletion first) with total count.

        Args:
            db: DB session.
            company_id: Tenant scope.
            limit: Page size (clamped by caller).
            offset: Offset.

        Returns:
            (tasks, total_count).
        """
        count_stmt = select(func.count(Task.id)).where(
            Task.deleted_at.is_not(None),
            Task.company_id == company_id,
        )
        total = (await db.execute(count_stmt)).scalar() or 0

        stmt = (
            select(Task)
            .options(
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            )
            .where(Task.deleted_at.is_not(None), Task.company_id == company_id)
            .order_by(Task.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total)
