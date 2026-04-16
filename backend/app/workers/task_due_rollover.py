"""Celery job: auto-extend overdue task due dates to the next calendar day."""

from __future__ import annotations

import logging

from app.workers.celery_app import celery_app
from app.workers.celery_async import run_coroutine

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.task_due_rollover.run_task_due_rollover")
def run_task_due_rollover() -> dict:
    """Run daily due-date rollover for unfinished tasks (see ``task_due_rollover_service``)."""
    from app.services.task_due_rollover_service import run_task_due_rollover_job

    try:
        result = run_coroutine(run_task_due_rollover_job())
    except Exception:
        logger.exception("run_task_due_rollover failed")
        raise
    logger.info("run_task_due_rollover done: %s", result)
    return result
