"""SLA monitoring background tasks.

Проверяет нарушения SLA и просроченные задачи,
отправляя уведомления ответственным лицам.
"""

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.workers.sla_monitor.check_sla_violations")
def check_sla_violations() -> dict:
    """Check all active tasks for SLA violations and send alerts.

    Возвращает:
        Количество обнаруженных нарушений.
    """
    logger.info("Checking SLA violations")
    # TODO: query tasks with sla_config, compare against elapsed time
    return {"violations_found": 0}


@celery_app.task(name="app.workers.sla_monitor.check_overdue_tasks")
def check_overdue_tasks() -> dict:
    """Check for tasks past their due date and notify assignees.

    Возвращает:
        Количество просроченных задач.
    """
    logger.info("Checking overdue tasks")
    return {"overdue_count": 0}
