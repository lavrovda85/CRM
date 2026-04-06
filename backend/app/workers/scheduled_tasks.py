"""Periodic Celery jobs for automatic task creation by environment schedule."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.models.task import Task
from app.services.task_notification_service import TaskNotificationService
from app.services.task_service import TaskService
from app.services.admin_settings_service import get_scheduler_rules
from app.workers.celery_app import celery_app
from app.workers.celery_async import run_coroutine

logger = logging.getLogger(__name__)


def _parse_uuid_opt(raw: str | None, field: str) -> uuid.UUID | None:
    """Parse UUID from env string and log invalid values."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        logger.warning("scheduled task config has invalid UUID", extra={"field": field, "value": text})
        return None


def _parse_uuid_list(raw_items: list[str], field: str) -> list[uuid.UUID]:
    """Parse list of UUID strings from env config with per-item validation."""
    out: list[uuid.UUID] = []
    for raw in raw_items:
        parsed = _parse_uuid_opt(raw, field)
        if parsed is not None:
            out.append(parsed)
    return out


def _match_cron_field(expr: str, value: int) -> bool:
    """Minimal cron matcher: '*', '*/n', 'a,b', 'x-y', single number."""
    text = str(expr or "*").strip()
    if text == "*" or not text:
        return True
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        if token.startswith("*/"):
            try:
                step = int(token[2:])
            except ValueError:
                continue
            if step > 0 and value % step == 0:
                return True
            continue
        if "-" in token:
            bounds = token.split("-", 1)
            try:
                lo = int(bounds[0].strip())
                hi = int(bounds[1].strip())
            except ValueError:
                continue
            if lo <= value <= hi:
                return True
            continue
        try:
            if int(token) == value:
                return True
        except ValueError:
            continue
    return False


def _is_due_now(cfg: dict[str, Any], now: datetime) -> bool:
    """Check if current UTC datetime matches scheduler cron settings."""
    weekday = now.weekday()  # Monday=0
    cron_weekday = (weekday + 1) % 7  # Cron: Sunday=0
    return (
        _match_cron_field(str(cfg.get("cron_minute", "*")), now.minute)
        and _match_cron_field(str(cfg.get("cron_hour", "*")), now.hour)
        and _match_cron_field(str(cfg.get("cron_day_of_month", "*")), now.day)
        and _match_cron_field(str(cfg.get("cron_month_of_year", "*")), now.month)
        and _match_cron_field(str(cfg.get("cron_day_of_week", "*")), cron_weekday)
    )


async def _run_create_env_scheduled_task() -> dict[str, Any]:
    """Create a task from env scheduler settings when enabled."""
    return await run_scheduler_rule_once()


async def _execute_rule(db, cfg: dict[str, Any], now: datetime) -> int:
    """Execute one scheduler rule once; returns 1 when task created, else 0."""
    if not bool(cfg.get("enabled", False)):
        return 0
    if not _is_due_now(cfg, now):
        return 0

    requester_id = _parse_uuid_opt(cfg.get("requested_by"), "TASK_SCHEDULER_REQUESTED_BY")
    assignee_id = _parse_uuid_opt(cfg.get("assigned_to"), "TASK_SCHEDULER_ASSIGNED_TO")
    creator_id = requester_id or assignee_id
    if creator_id is None:
        logger.warning(
            "scheduled task skipped: creator id missing",
            extra={"requested_by": cfg.get("requested_by"), "assigned_to": cfg.get("assigned_to")},
        )
        return 0

    dedup_window = int(cfg.get("dedup_window_minutes", 180))
    dedup_since = now - timedelta(minutes=dedup_window)
    due_date = now + timedelta(hours=int(cfg.get("due_in_hours", 24)))

    payload: dict[str, Any] = {
        "title": str(cfg.get("title") or "Scheduled task"),
        "description": cfg.get("description"),
        "priority": str(cfg.get("priority") or "medium"),
        "assigned_to": assignee_id,
        "requested_by": requester_id,
        "template_id": _parse_uuid_opt(cfg.get("template_id"), "TASK_SCHEDULER_TEMPLATE_ID"),
        "board_id": _parse_uuid_opt(cfg.get("board_id"), "TASK_SCHEDULER_BOARD_ID"),
        "client_id": _parse_uuid_opt(cfg.get("client_id"), "TASK_SCHEDULER_CLIENT_ID"),
        "due_date": due_date,
        "observer_ids": _parse_uuid_list(
            list(cfg.get("observer_ids") or []),
            "TASK_SCHEDULER_OBSERVER_IDS",
        ),
        "co_assignee_ids": _parse_uuid_list(
            list(cfg.get("co_assignee_ids") or []),
            "TASK_SCHEDULER_CO_ASSIGNEE_IDS",
        ),
        "custom_fields": {
            "scheduler_source": "env+db",
            "scheduler_rule_id": str(cfg.get("id") or ""),
            "scheduler_rule_name": str(cfg.get("name") or ""),
            "scheduler_window_minutes": dedup_window,
            "scheduled_at": now.isoformat(),
        },
    }

    exists_stmt = (
        select(Task.id)
        .where(Task.active_filter())
        .where(Task.title == payload["title"])
        .where(Task.created_by == creator_id)
        .where(Task.created_at >= dedup_since)
        .limit(1)
    )
    exists = (await db.execute(exists_stmt)).scalar_one_or_none()
    if exists is not None:
        return 0

    task = await TaskService.create_task(db, payload, user={"id": creator_id})
    loaded = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.template),
            selectinload(Task.creator),
            selectinload(Task.requester_user),
            selectinload(Task.co_assignees),
            selectinload(Task.observers),
        )
        .where(Task.id == task.id),
    )
    task_for_notify = loaded.scalar_one()
    await TaskNotificationService.notify_after_task_created(db, task_for_notify, creator_id)
    return 1


async def run_scheduler_rule_once(rule_id: str | None = None, force: bool = False) -> dict[str, Any]:
    """Run all enabled rules (or a specific rule) once."""
    async with async_session_factory() as db:
        try:
            now = datetime.now(timezone.utc)
            rules = await get_scheduler_rules(db)
            created_count = 0
            for cfg in rules:
                if rule_id and str(cfg.get("id")) != rule_id:
                    continue
                if not force and not _is_due_now(cfg, now):
                    continue
                created_count += await _execute_rule(db, cfg, now)
            await db.commit()
            return {"created": created_count, "rules_total": len(rules), "rule_id": rule_id or ""}
        except Exception:
            await db.rollback()
            raise


@celery_app.task(name="app.workers.scheduled_tasks.create_env_scheduled_task")
def create_env_scheduled_task() -> dict[str, Any]:
    """Celery task wrapper for env-driven scheduled task creation."""
    try:
        result = run_coroutine(_run_create_env_scheduled_task())
    except Exception:
        logger.exception("create_env_scheduled_task failed")
        raise
    logger.info("create_env_scheduled_task done: %s", result)
    return result

