"""Celery application configuration.

Настраивает Celery с Redis в качестве брокера
и регистрирует периодические задачи.
"""

import os

from celery import Celery
from celery.schedules import crontab

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/1")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/2")

celery_app = Celery(
    "hvac_crm",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.workers.notifications",
        "app.workers.sla_monitor",
        "app.workers.reports",
        "app.workers.depreciation_calc",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "check-sla-violations": {
        "task": "app.workers.sla_monitor.check_sla_violations",
        "schedule": crontab(minute="*/15"),
    },
    "calculate-monthly-depreciation": {
        "task": "app.workers.depreciation_calc.calculate_monthly_depreciation",
        "schedule": crontab(day_of_month="1", hour="2", minute="0"),
    },
    "send-daily-summary": {
        "task": "app.workers.reports.send_daily_summary",
        "schedule": crontab(hour="20", minute="0"),
    },
    "check-overdue-tasks": {
        "task": "app.workers.sla_monitor.check_overdue_tasks",
        "schedule": crontab(minute="*/30"),
    },
}
