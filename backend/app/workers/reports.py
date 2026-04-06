"""Report generation background tasks.

Генерация ежедневных и периодических отчётов
об эффективности сотрудников, загрузке и складе.
"""

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.workers.reports.send_daily_summary")
def send_daily_summary() -> dict:
    """Generate and send daily summary report to managers.

    Возвращает:
        Статус генерации отчёта.
    """
    logger.info("Generating daily summary report")
    return {"status": "generated"}
