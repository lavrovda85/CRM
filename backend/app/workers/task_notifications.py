"""Periodic Celery jobs for task deadline / overdue in-app notifications."""

from __future__ import annotations

import logging

from app.workers.celery_app import celery_app
from app.workers.celery_async import run_coroutine

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.task_notifications.scan_task_deadlines")
def scan_task_deadlines() -> dict:
    """Scan active tasks and create in-app notifications for due dates and overdue."""
    from app.services.task_notification_service import run_periodic_task_notification_scans

    try:
        result = run_coroutine(run_periodic_task_notification_scans())
    except Exception:
        logger.exception("scan_task_deadlines failed")
        raise
    logger.info("scan_task_deadlines done: %s", result)
    return result
