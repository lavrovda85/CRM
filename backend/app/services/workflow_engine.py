"""Core workflow engine — validates and executes task status transitions.

Движок конечного автомата задач. Проверяет допустимость переходов,
выполняет проверку ролей, чек-листов, документов и обязательных полей,
запускает автоматические действия (списание со склада, завершение
тайм-трекинга, уведомления) и записывает историю переходов.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    NotFoundError,
    WarehouseInsufficientStockError,
    WorkflowTransitionError,
)
from app.models.checklist import Checklist
from app.models.document import Document
from app.models.notification import Notification
from app.models.task import Task
from app.models.task_status import TaskStatusHistory
from app.models.task_template import TaskTemplate
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.models.warehouse_item import WarehouseItem
from app.models.warehouse_movement import WarehouseMovement
from app.schemas.template import WorkflowDefinition, WorkflowTransition

if TYPE_CHECKING:
    from app.core.security import CurrentUser

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Finite-state machine engine for task status transitions.

    Атрибуты:
        _db: Асинхронная сессия БД.
        _user: Текущий аутентифицированный пользователь.
    """

    def __init__(self, db: AsyncSession, user: "CurrentUser") -> None:
        """Initialize the workflow engine.

        Аргументы:
            db: Асинхронная сессия SQLAlchemy.
            user: Текущий пользователь из JWT (CurrentUser dataclass).
        """
        self._db = db
        self._user = user

    async def validate_transition(
        self,
        task: Task,
        from_status: str,
        to_status: str,
        user: "CurrentUser",
        db: AsyncSession,
    ) -> list[str]:
        """Validate whether a transition is allowed without executing it.

        Аргументы:
            task: ORM-объект задачи.
            from_status: Текущий статус задачи.
            to_status: Целевой статус.
            user: Пользователь, инициирующий переход.
            db: Сессия БД для запросов.

        Возвращает:
            Список строк с описанием ошибок. Пустой список означает,
            что переход допустим.
        """
        errors: list[str] = []

        workflow_def, transition = await self._resolve_transition(
            task, from_status, to_status
        )
        if workflow_def is None or transition is None:
            errors.append(
                f"Transition '{from_status}' -> '{to_status}' is not defined in the workflow"
            )
            return errors

        errors.extend(self._check_required_roles(transition, user))
        errors.extend(await self._check_required_fields(task, transition))
        errors.extend(await self._check_required_checklists(task, transition, db))
        errors.extend(await self._check_required_documents(task, transition, db))

        return errors

    async def execute_transition(
        self,
        task: Task,
        to_status: str,
        user: "CurrentUser",
        db: AsyncSession,
        reason: str | None = None,
        checklist_data: dict[str, Any] | None = None,
    ) -> Task:
        """Validate and execute a status transition, including auto-actions.

        Аргументы:
            task: ORM-объект задачи.
            to_status: Целевой статус.
            user: Пользователь, инициирующий переход.
            db: Сессия БД.
            reason: Комментарий к переходу (опционально).
            checklist_data: Дополнительные данные по чек-листам (опционально).

        Возвращает:
            Обновлённый ORM-объект задачи.

        Raises:
            WorkflowTransitionError: Если переход запрещён.
        """
        from_status = task.status
        task_id_str = str(task.id)

        errors = await self.validate_transition(task, from_status, to_status, user, db)
        if errors:
            raise WorkflowTransitionError(
                task_id=task_id_str,
                from_status=from_status,
                to_status=to_status,
                reason="; ".join(errors),
            )

        _, transition = await self._resolve_transition(task, from_status, to_status)

        db_user = await self._resolve_db_user(user, db)

        task.status = to_status
        self._apply_lifecycle_timestamps(task, to_status)

        history = TaskStatusHistory(
            task_id=task.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=db_user.id,
            reason=reason,
            transition_data=checklist_data or {},
        )
        db.add(history)

        if transition is not None:
            await self._run_auto_actions(
                task, transition, db_user, db
            )

        await db.flush()
        logger.info(
            "Task transition executed",
            extra={
                "task_id": task_id_str,
                "from": from_status,
                "to": to_status,
                "user": user.sub,
            },
        )
        return task

    def get_available_transitions(
        self, task: Task, user: "CurrentUser"
    ) -> list[dict[str, Any]]:
        """Return a list of transitions available from the current task status.

        Аргументы:
            task: ORM-объект задачи с загруженным template.
            user: Текущий пользователь.

        Возвращает:
            Список словарей с ключами "from", "to", "required_roles",
            "required_fields", "required_checklists", "required_documents",
            "allowed" (bool — может ли данный пользователь выполнить переход
            по роли).
        """
        if task.template is None or not task.template.workflow_definition:
            return []

        raw = task.template.workflow_definition
        transitions_raw = raw.get("transitions", [])
        current = task.status
        result: list[dict[str, Any]] = []

        for t in transitions_raw:
            if t.get("from") != current:
                continue

            required_roles = t.get("required_roles", [])
            allowed = not required_roles or any(
                r in user.roles for r in required_roles
            )

            result.append({
                "from": t["from"],
                "to": t["to"],
                "required_roles": required_roles,
                "required_fields": t.get("required_fields", []),
                "required_checklists": t.get("required_checklists", []),
                "required_documents": t.get("required_documents", []),
                "allowed": allowed,
            })

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _resolve_transition(
        self, task: Task, from_status: str, to_status: str
    ) -> tuple[WorkflowDefinition | None, WorkflowTransition | None]:
        """Load and parse the workflow definition, then find the matching transition.

        Аргументы:
            task: ORM-объект задачи.
            from_status: Исходный статус.
            to_status: Целевой статус.

        Возвращает:
            Кортеж (WorkflowDefinition, WorkflowTransition) или (None, None),
            если workflow не определён или переход не найден.
        """
        template = task.template
        if template is None or not template.workflow_definition:
            return None, None

        raw: dict[str, Any] = template.workflow_definition
        try:
            workflow = WorkflowDefinition.model_validate(raw)
        except Exception:
            logger.warning(
                "Invalid workflow_definition in template %s", template.id
            )
            return None, None

        for t in workflow.transitions:
            if t.from_state == from_status and t.to == to_status:
                return workflow, t

        return workflow, None

    @staticmethod
    def _check_required_roles(
        transition: WorkflowTransition, user: "CurrentUser"
    ) -> list[str]:
        """Verify the user has at least one of the required roles.

        Аргументы:
            transition: Объект перехода из workflow.
            user: Текущий пользователь.

        Возвращает:
            Список ошибок (пустой, если роли удовлетворяют).
        """
        if not transition.required_roles:
            return []
        if any(role in user.roles for role in transition.required_roles):
            return []
        return [
            f"User lacks required role(s): {', '.join(transition.required_roles)}"
        ]

    @staticmethod
    async def _check_required_fields(
        task: Task, transition: WorkflowTransition
    ) -> list[str]:
        """Verify all required fields have non-empty values.

        Аргументы:
            task: ORM-объект задачи.
            transition: Объект перехода.

        Возвращает:
            Список ошибок для незаполненных полей.
        """
        errors: list[str] = []
        custom = task.custom_fields or {}

        for field_key in transition.required_fields:
            value = getattr(task, field_key, None)
            if value is None:
                value = custom.get(field_key)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"Required field '{field_key}' is empty")

        return errors

    @staticmethod
    async def _check_required_checklists(
        task: Task, transition: WorkflowTransition, db: AsyncSession
    ) -> list[str]:
        """Verify all gate checklists for this transition are completed.

        Аргументы:
            task: ORM-объект задачи.
            transition: Объект перехода.
            db: Сессия БД.

        Возвращает:
            Список ошибок для незавершённых чек-листов.
        """
        if not transition.required_checklists:
            return []

        gate_key = f"{transition.from_state}->{transition.to}"
        stmt = (
            select(Checklist)
            .where(Checklist.task_id == task.id)
            .where(
                Checklist.gate_transition.in_([gate_key, *transition.required_checklists])
                | Checklist.title.in_(transition.required_checklists)
            )
        )
        result = await db.execute(stmt)
        checklists = result.scalars().all()

        found_ids = {cl.title for cl in checklists}
        errors: list[str] = []

        for req in transition.required_checklists:
            matching = [cl for cl in checklists if cl.title == req or cl.gate_transition == gate_key]
            if not matching:
                errors.append(f"Required checklist '{req}' not found on task")
            elif not all(cl.is_completed for cl in matching):
                errors.append(f"Checklist '{req}' is not fully completed")

        return errors

    @staticmethod
    async def _check_required_documents(
        task: Task, transition: WorkflowTransition, db: AsyncSession
    ) -> list[str]:
        """Verify minimum document counts by type are met.

        Аргументы:
            task: ORM-объект задачи.
            transition: Объект перехода.
            db: Сессия БД.

        Возвращает:
            Список ошибок для недостающих документов.
        """
        if not transition.required_documents:
            return []

        doc_types = [rd.type for rd in transition.required_documents]
        stmt = (
            select(Document.doc_type, func.count(Document.id))
            .where(Document.task_id == task.id)
            .where(Document.doc_type.in_(doc_types))
            .group_by(Document.doc_type)
        )
        result = await db.execute(stmt)
        counts: dict[str, int] = dict(result.all())

        errors: list[str] = []
        for req_doc in transition.required_documents:
            actual = counts.get(req_doc.type, 0)
            if actual < req_doc.min_count:
                errors.append(
                    f"Required {req_doc.min_count} document(s) of type "
                    f"'{req_doc.type}', found {actual}"
                )
        return errors

    @staticmethod
    def _apply_lifecycle_timestamps(task: Task, to_status: str) -> None:
        """Set started_at / completed_at based on workflow state semantics.

        Аргументы:
            task: ORM-объект задачи.
            to_status: Новый статус после перехода.
        """
        now = datetime.now(timezone.utc)
        if task.started_at is None and to_status not in ("new", "cancelled"):
            task.started_at = now
        if to_status in ("completed", "done", "closed"):
            task.completed_at = now

    async def _resolve_db_user(
        self, user: "CurrentUser", db: AsyncSession
    ) -> User:
        """Resolve CurrentUser (JWT) to the database User record.

        Аргументы:
            user: JWT-данные текущего пользователя.
            db: Сессия БД.

        Возвращает:
            ORM-объект User.

        Raises:
            NotFoundError: Если пользователь не найден в БД.
        """
        stmt = select(User).where(User.keycloak_id == user.sub)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()
        if db_user is None:
            raise NotFoundError("User", user.sub)
        return db_user

    async def _run_auto_actions(
        self,
        task: Task,
        transition: WorkflowTransition,
        db_user: User,
        db: AsyncSession,
    ) -> None:
        """Execute all auto_actions defined on the transition.

        Аргументы:
            task: ORM-объект задачи.
            transition: Объект перехода с auto_actions.
            db_user: ORM-объект пользователя, инициировавшего переход.
            db: Сессия БД.
        """
        for action in transition.auto_actions:
            try:
                if action.type == "deduct_warehouse":
                    await self._action_deduct_warehouse(task, action, db_user, db)
                elif action.type == "complete_time_entry":
                    await self._action_complete_time_entry(task, db_user, db)
                elif action.type == "notify":
                    await self._action_notify(task, action, db_user, db)
                else:
                    logger.warning(
                        "Unknown auto_action type '%s' on task %s",
                        action.type,
                        task.id,
                    )
            except WarehouseInsufficientStockError:
                raise
            except Exception:
                logger.exception(
                    "Auto-action '%s' failed for task %s", action.type, task.id
                )

    @staticmethod
    async def _action_deduct_warehouse(
        task: Task,
        action: Any,
        db_user: User,
        db: AsyncSession,
    ) -> None:
        """Deduct materials from warehouse based on task custom_fields.

        Аргументы:
            task: ORM-объект задачи.
            action: Описание действия из auto_actions.
            db_user: Пользователь, инициировавший переход.
            db: Сессия БД.

        Raises:
            WarehouseInsufficientStockError: Если на складе недостаточно товара.
        """
        field_key = action.from_field or "materials_used"
        materials: list[dict[str, Any]] = (task.custom_fields or {}).get(field_key, [])
        if not isinstance(materials, list):
            return

        for mat in materials:
            item_id = mat.get("item_id")
            qty = mat.get("quantity", 0)
            if not item_id or not qty:
                continue

            stmt = select(WarehouseItem).where(WarehouseItem.id == uuid.UUID(str(item_id)))
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()
            if item is None:
                logger.warning("Warehouse item %s not found, skipping deduction", item_id)
                continue

            available = item.quantity - item.reserved_quantity
            qty_decimal = Decimal(str(qty))
            if available < qty_decimal:
                raise WarehouseInsufficientStockError(
                    item_id=str(item.id),
                    requested=float(qty_decimal),
                    available=float(available),
                )

            item.quantity -= qty_decimal

            movement = WarehouseMovement(
                item_id=item.id,
                task_id=task.id,
                user_id=db_user.id,
                movement_type="consumption",
                quantity=qty_decimal,
                unit_price=item.price,
                reason=f"Auto-deduct on transition to '{task.status}'",
            )
            db.add(movement)

    @staticmethod
    async def _action_complete_time_entry(
        task: Task, db_user: User, db: AsyncSession
    ) -> None:
        """Close any open (running) time entries for this task.

        Аргументы:
            task: ORM-объект задачи.
            db_user: Пользователь, инициировавший переход.
            db: Сессия БД.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(TimeEntry)
            .where(TimeEntry.task_id == task.id)
            .where(TimeEntry.ended_at.is_(None))
            .where(TimeEntry.started_at.isnot(None))
        )
        result = await db.execute(stmt)
        open_entries = result.scalars().all()

        for entry in open_entries:
            entry.ended_at = now
            if entry.started_at:
                delta = now - entry.started_at
                entry.duration_minutes = int(delta.total_seconds() / 60)

        if open_entries:
            logger.info(
                "Closed %d open time entries for task %s",
                len(open_entries),
                task.id,
            )

    @staticmethod
    async def _action_notify(
        task: Task,
        action: Any,
        db_user: User,
        db: AsyncSession,
    ) -> None:
        """Create a notification record and dispatch via Celery.

        Аргументы:
            task: ORM-объект задачи.
            action: Описание действия из auto_actions.
            db_user: Пользователь, инициировавший переход.
            db: Сессия БД.
        """
        from app.workers.notifications import send_task_notification

        channel = action.channel or "web_push"
        template_name = action.template or "status_changed"

        from app.models.task import task_co_assignees

        recipients: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()

        def _add_recipient(uid: uuid.UUID | None) -> None:
            if uid is None or uid in seen:
                return
            seen.add(uid)
            recipients.append(uid)

        _add_recipient(task.assigned_to)
        _add_recipient(task.requested_by)
        _add_recipient(task.created_by)
        co_res = await db.execute(
            select(task_co_assignees.c.user_id).where(task_co_assignees.c.task_id == task.id)
        )
        for row in co_res.all():
            _add_recipient(row[0])

        for recipient_id in recipients:
            notification = Notification(
                company_id=task.company_id,
                user_id=recipient_id,
                channel=channel,
                event_type=template_name,
                title=f"Task '{task.title}' status changed",
                body=f"Status changed to '{task.status}' by {db_user.full_name}",
                data={
                    "task_id": str(task.id),
                    "new_status": task.status,
                    "changed_by": str(db_user.id),
                },
            )
            db.add(notification)

        send_task_notification.delay(
            task_id=str(task.id),
            event="status_changed",
            recipients=[str(r) for r in recipients],
        )

        logger.info(
            "Notification dispatched for task %s to %d recipient(s)",
            task.id,
            len(recipients),
        )
