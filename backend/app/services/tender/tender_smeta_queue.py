"""Celery enqueue helper for tender smeta (estimate) jobs."""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def schedule_tender_smeta(tender_id: uuid.UUID) -> None:
    """Send ``run_tender_smeta`` Celery task for ``tender_id``."""
    try:
        from app.workers.tender_smeta import run_tender_smeta_task

        run_tender_smeta_task.delay(str(tender_id))
    except Exception as exc:
        logger.warning("Could not queue tender_smeta for %s: %s", tender_id, exc)
