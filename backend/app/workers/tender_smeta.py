"""Celery tasks for async tender smeta (estimate) from bill of works."""

from __future__ import annotations

import logging
import uuid

from app.workers.celery_app import celery_app
from app.workers.celery_async import run_coroutine

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tender_smeta.run_tender_smeta",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_tender_smeta_task(self, tender_id_str: str) -> dict[str, str]:
    """Run ``run_tender_smeta_job`` in the worker event loop."""
    try:
        tid = uuid.UUID(tender_id_str)
    except ValueError:
        logger.error("Invalid tender_id for smeta: %r", tender_id_str)
        return {"tender_id": tender_id_str, "ok": False, "error": "invalid_uuid"}

    try:
        from app.services.tender.tender_smeta_service import run_tender_smeta_job

        run_coroutine(run_tender_smeta_job(tid))
    except Exception as exc:
        logger.exception("tender_smeta task failed for %s", tender_id_str)
        raise self.retry(exc=exc) from exc

    return {"tender_id": tender_id_str, "ok": True}
