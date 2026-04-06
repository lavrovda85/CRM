"""Enqueue tender document analysis jobs (Celery).

Schedules background processing after DB commits; failures are logged without raising.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def schedule_tender_analysis(tender_id: uuid.UUID) -> None:
    """Send ``run_tender_analysis`` Celery task for ``tender_id``.

    Safe to call after commit; import errors are logged only.
    """
    try:
        from app.workers.tender_analysis import run_tender_analysis_task

        run_tender_analysis_task.delay(str(tender_id))
    except Exception as exc:
        logger.warning("Could not queue tender_analysis for %s: %s", tender_id, exc)
