"""In-app notifications for task lifecycle: assignment, updates, deadlines.

Creates ``Notification`` rows for assignees, requesters, and co-assignees.
Used from REST handlers and from periodic Celery scans.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification
from app.models.task import Task
from app.models.user import User

_TERMINAL = frozenset({"completed", "done", "closed"})


class TaskNotificationService:
    """Build participant lists and insert in-app ``Notification`` rows."""

    @staticmethod
    def participant_user_ids(task: Task) -> list[uuid.UUID]:
        """Unique user IDs involved in the task.

        Includes:
            - primary assignee
            - requester / creator
            - co-assignees
            - observers (watchers)
        """
        seen: set[uuid.UUID] = set()
        ordered: list[uuid.UUID] = []
        for uid in (task.assigned_to, task.requested_by, task.created_by):
            if uid is not None and uid not in seen:
                seen.add(uid)
                ordered.append(uid)
        for u in task.co_assignees or []:
            if u.id not in seen:
                seen.add(u.id)
                ordered.append(u.id)
        for u in task.observers or []:
            if u.id not in seen:
                seen.add(u.id)
                ordered.append(u.id)
        return ordered

    @staticmethod
    async def filter_active_user_ids(db: AsyncSession, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        if not ids:
            return []
        res = await db.execute(select(User.id).where(User.id.in_(ids), User.is_active.is_(True)))
        return [row[0] for row in res.all()]

    @staticmethod
    async def has_recent_duplicate(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        event_type: str,
        task_id: uuid.UUID,
        dedupe_key: str | None,
        within_hours: float,
    ) -> bool:
        """Return True if a matching notification was created recently (spam guard)."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        conds: list[Any] = [
            Notification.user_id == user_id,
            Notification.event_type == event_type,
            Notification.created_at >= threshold,
            Notification.data.contains({"task_id": str(task_id)}),
        ]
        if dedupe_key is not None:
            conds.append(Notification.data.contains({"dedupe_key": dedupe_key}))
        q = select(func.count(Notification.id)).where(and_(*conds))
        n = (await db.execute(q)).scalar() or 0
        return n > 0

    @staticmethod
    async def _insert(
        db: AsyncSession,
        *,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: str,
        title: str,
        body: str,
        data: dict[str, Any],
    ) -> None:
        db.add(
            Notification(
                company_id=company_id,
                user_id=user_id,
                channel="web_push",
                event_type=event_type,
                title=title,
                body=body,
                data=data,
                is_read=False,
                is_delivered=True,
            )
        )

    @staticmethod
    async def notify_after_task_created(db: AsyncSession, task: Task, actor_id: uuid.UUID) -> None:
        """Notify assignee and co-assignees when a task is created (skip actor)."""
        tid = str(task.id)
        cid = task.company_id
        if task.assigned_to and task.assigned_to != actor_id:
            for uid in await TaskNotificationService.filter_active_user_ids(db, [task.assigned_to]):
                await TaskNotificationService._insert(
                    db,
                    company_id=cid,
                    user_id=uid,
                    event_type="task_assigned",
                    title="Вам назначена задача",
                    body=f"«{task.title}»",
                    data={"task_id": tid, "kind": "created_assigned"},
                )
        co_ids = [u.id for u in (task.co_assignees or []) if u.id != actor_id]
        if task.assigned_to:
            co_ids = [c for c in co_ids if c != task.assigned_to]
        for uid in await TaskNotificationService.filter_active_user_ids(db, co_ids):
            await TaskNotificationService._insert(
                db,
                company_id=cid,
                user_id=uid,
                event_type="task_assigned",
                title="Вы соисполнитель",
                body=f"Задача «{task.title}»",
                data={"task_id": tid, "kind": "created_co_assignee"},
            )

        obs_ids = [u.id for u in (task.observers or []) if u.id != actor_id]
        # Avoid duplicating observer notifications for users who already got
        # an "assigned/co-assignee" notification.
        if task.assigned_to:
            obs_ids = [o for o in obs_ids if o != task.assigned_to]
        co_set = {u.id for u in (task.co_assignees or [])}
        obs_ids = [o for o in obs_ids if o not in co_set]

        for uid in await TaskNotificationService.filter_active_user_ids(db, obs_ids):
            await TaskNotificationService._insert(
                db,
                company_id=cid,
                user_id=uid,
                event_type="task_observed",
                title="Вы наблюдаете задачу",
                body=f"«{task.title}»",
                data={"task_id": tid, "kind": "created_observer"},
            )

    @staticmethod
    async def notify_assignee_change(
        db: AsyncSession,
        task: Task,
        *,
        prev_assignee: uuid.UUID | None,
        new_assignee: uuid.UUID | None,
        actor_id: uuid.UUID,
    ) -> None:
        """Notify newly assigned user; optional message when removed (if not actor)."""
        tid = str(task.id)
        cid = task.company_id
        if new_assignee and new_assignee != prev_assignee and new_assignee != actor_id:
            for uid in await TaskNotificationService.filter_active_user_ids(db, [new_assignee]):
                await TaskNotificationService._insert(
                    db,
                    company_id=cid,
                    user_id=uid,
                    event_type="task_assigned",
                    title="Вам назначена задача",
                    body=f"«{task.title}»",
                    data={"task_id": tid, "kind": "reassigned"},
                )
        if prev_assignee and new_assignee != prev_assignee and prev_assignee != actor_id:
            for uid in await TaskNotificationService.filter_active_user_ids(db, [prev_assignee]):
                await TaskNotificationService._insert(
                    db,
                    company_id=cid,
                    user_id=uid,
                    event_type="task_updated",
                    title="Снято назначение",
                    body=f"Задача «{task.title}» назначена другому исполнителю",
                    data={"task_id": tid, "kind": "unassigned"},
                )

        # Notify task observers about assignee change for control purposes.
        obs_ids = [u.id for u in (task.observers or []) if u.id != actor_id]
        if new_assignee:
            obs_ids = [o for o in obs_ids if o != new_assignee]
        if prev_assignee:
            obs_ids = [o for o in obs_ids if o != prev_assignee]

        if new_assignee or prev_assignee:
            msg_kind = "assignee_changed" if new_assignee != prev_assignee else "assignee_updated"
            body = (
                f"«{task.title}» изменён исполнитель"
                if new_assignee and prev_assignee
                else f"«{task.title}» изменён исполнитель"
            )
            for uid in await TaskNotificationService.filter_active_user_ids(db, obs_ids):
                await TaskNotificationService._insert(
                    db,
                    company_id=cid,
                    user_id=uid,
                    event_type="task_updated",
                    title="Исполнитель обновлён",
                    body=body,
                    data={
                        "task_id": tid,
                        "kind": msg_kind,
                        "from_assigned_to": str(prev_assignee) if prev_assignee else None,
                        "to_assigned_to": str(new_assignee) if new_assignee else None,
                    },
                )

    @staticmethod
    async def notify_task_fields_changed(
        db: AsyncSession,
        task: Task,
        *,
        actor_id: uuid.UUID,
        changed: set[str],
    ) -> None:
        """Notify participants about due date / priority / title changes (except actor)."""
        if not changed.intersection({"due_date", "priority", "title", "co_assignees"}):
            return
        parts: list[str] = []
        if "due_date" in changed:
            parts.append("срок")
        if "priority" in changed:
            parts.append("приоритет")
        if "title" in changed:
            parts.append("название")
        if "co_assignees" in changed:
            parts.append("соисполнители")
        summary = ", ".join(parts)
        recipients = [u for u in TaskNotificationService.participant_user_ids(task) if u != actor_id]
        for uid in await TaskNotificationService.filter_active_user_ids(db, recipients):
            await TaskNotificationService._insert(
                db,
                company_id=task.company_id,
                user_id=uid,
                event_type="task_updated",
                title="Задача изменена",
                body=f"«{task.title}»: обновлены {summary}",
                data={"task_id": str(task.id), "kind": "fields", "fields": list(changed)},
            )

    @staticmethod
    async def notify_observers_status_changed(
        db: AsyncSession,
        task: Task,
        *,
        actor_id: uuid.UUID,
        from_status: str,
        to_status: str,
    ) -> None:
        """Notify observers about status transitions (for execution control)."""
        obs_ids = [u.id for u in (task.observers or []) if u.id != actor_id]
        if not obs_ids:
            return

        recipients = await TaskNotificationService.filter_active_user_ids(db, obs_ids)
        tid = str(task.id)
        for uid in recipients:
            await TaskNotificationService._insert(
                db,
                company_id=task.company_id,
                user_id=uid,
                event_type="task_updated",
                title="Статус задачи изменён",
                body=f"«{task.title}»: {from_status} -> {to_status}",
                data={
                    "task_id": tid,
                    "kind": "status_changed",
                    "from_status": from_status,
                    "to_status": to_status,
                },
            )

    @staticmethod
    async def scan_due_within_24h(db: AsyncSession) -> int:
        """Notify participants about tasks due within the next 24 hours."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=24)
        stmt = (
            select(Task)
            .options(selectinload(Task.co_assignees), selectinload(Task.observers))
            .where(
                Task.active_filter(),
                Task.due_date.is_not(None),
                Task.due_date > now,
                Task.due_date <= window_end,
                Task.status.not_in(_TERMINAL),
            )
        )
        result = await db.execute(stmt)
        tasks = list(result.scalars().unique().all())
        added = 0
        for task in tasks:
            due_day = task.due_date.date().isoformat() if task.due_date else ""
            dedupe_key = f"due24h_{task.id}_{due_day}"
            for uid in TaskNotificationService.participant_user_ids(task):
                if await TaskNotificationService.has_recent_duplicate(
                    db,
                    user_id=uid,
                    event_type="task_due_soon",
                    task_id=task.id,
                    dedupe_key=dedupe_key,
                    within_hours=20.0,
                ):
                    continue
                active = await TaskNotificationService.filter_active_user_ids(db, [uid])
                if not active:
                    continue
                due_s = task.due_date.isoformat() if task.due_date else ""
                await TaskNotificationService._insert(
                    db,
                    company_id=task.company_id,
                    user_id=uid,
                    event_type="task_due_soon",
                    title="Скоро дедлайн",
                    body=f"«{task.title}» — срок {due_s}",
                    data={
                        "task_id": str(task.id),
                        "dedupe_key": dedupe_key,
                        "due_date": due_s,
                    },
                )
                added += 1
        return added

    @staticmethod
    async def scan_overdue(db: AsyncSession) -> int:
        """Daily-style reminder for overdue active tasks."""
        now = datetime.now(timezone.utc)
        day_key = now.date().isoformat()
        dedupe_key = f"overdue_{day_key}"
        stmt = (
            select(Task)
            .options(selectinload(Task.co_assignees), selectinload(Task.observers))
            .where(
                Task.active_filter(),
                Task.due_date.is_not(None),
                Task.due_date < now,
                Task.status.not_in(_TERMINAL),
            )
        )
        result = await db.execute(stmt)
        tasks = list(result.scalars().unique().all())
        added = 0
        for task in tasks:
            for uid in TaskNotificationService.participant_user_ids(task):
                if await TaskNotificationService.has_recent_duplicate(
                    db,
                    user_id=uid,
                    event_type="task_overdue",
                    task_id=task.id,
                    dedupe_key=dedupe_key,
                    within_hours=20.0,
                ):
                    continue
                active = await TaskNotificationService.filter_active_user_ids(db, [uid])
                if not active:
                    continue
                due_s = task.due_date.isoformat() if task.due_date else ""
                await TaskNotificationService._insert(
                    db,
                    company_id=task.company_id,
                    user_id=uid,
                    event_type="task_overdue",
                    title="Просрочен срок",
                    body=f"«{task.title}» — было до {due_s}",
                    data={
                        "task_id": str(task.id),
                        "dedupe_key": dedupe_key,
                        "due_date": due_s,
                    },
                )
                added += 1
        return added


async def run_periodic_task_notification_scans() -> dict[str, int]:
    """Run due-soon and overdue scans in one Celery job (commits once)."""
    from app.core.database import async_session_factory

    async with async_session_factory() as db:
        due_n = await TaskNotificationService.scan_due_within_24h(db)
        over_n = await TaskNotificationService.scan_overdue(db)
        await db.commit()
    return {"due_soon_notifications": due_n, "overdue_notifications": over_n}
