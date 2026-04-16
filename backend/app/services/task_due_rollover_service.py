"""Daily rollover of overdue task due dates to the next calendar day.

Незавершённые задачи (не терминальный статус, не soft-delete) с дедлайном
в прошлом по календарю в заданной IANA-таймзоне получают ``due_date`` на
завтрашний день с сохранением локального времени суток.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.services.task_due_rollover_logic import compute_next_day_same_local_time

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "done", "closed"})


async def rollover_overdue_task_due_dates(
    db: AsyncSession,
    *,
    timezone_name: str,
    reference_now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Bump ``due_date`` to next local calendar day for eligible overdue tasks.

    Eligible rows: not soft-deleted, ``completed_at`` is NULL, status not terminal,
    ``due_date`` set, and the due date's calendar day in ``timezone_name`` is strictly
    before today's calendar day in that zone.

    Args:
        db: Async SQLAlchemy session.
        timezone_name: IANA zone for day boundaries.
        reference_now_utc: Optional fixed "now" (UTC) for tests.

    Returns:
        Dict with ``updated`` (count) and ``task_ids`` (list of UUID strings, capped at 500 for logs).
    """
    now_utc = reference_now_utc or datetime.now(timezone.utc)
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.error("task due rollover skipped: invalid timezone %r", timezone_name)
        return {"updated": 0, "task_ids": [], "error": "invalid_timezone"}

    stmt = select(Task).where(
        Task.active_filter(),
        Task.due_date.is_not(None),
        Task.completed_at.is_(None),
        Task.status.not_in(_TERMINAL_STATUSES),
    )
    result = await db.execute(stmt)
    tasks: list[Task] = list(result.scalars().unique().all())

    updated_ids: list[uuid.UUID] = []
    for task in tasks:
        if task.due_date is None:
            continue
        try:
            new_due = compute_next_day_same_local_time(
                task.due_date,
                tz_name=timezone_name,
                reference_now_utc=now_utc,
            )
        except ValueError:
            continue
        if new_due == task.due_date:
            continue
        task.due_date = new_due
        updated_ids.append(task.id)

    await db.commit()
    id_strs = [str(i) for i in updated_ids[:500]]
    logger.info(
        "task due rollover: updated=%s timezone=%s",
        len(updated_ids),
        timezone_name,
    )
    return {"updated": len(updated_ids), "task_ids": id_strs}


async def run_task_due_rollover_job() -> dict[str, Any]:
    """Entry point for Celery: load settings and run rollover in one transaction."""
    from app.core.config import get_settings
    from app.core.database import async_session_factory

    settings = get_settings()
    if not settings.task_due_rollover_enabled:
        return {"skipped": True, "updated": 0, "task_ids": []}

    async with async_session_factory() as db:
        return await rollover_overdue_task_due_dates(
            db,
            timezone_name=settings.task_due_rollover_timezone,
        )
