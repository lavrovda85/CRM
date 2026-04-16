"""Celery application configuration.

Настраивает Celery с Redis в качестве брокера
и регистрирует периодические задачи.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import get_settings

settings = get_settings()
broker_url = settings.celery_broker_url
result_backend = settings.celery_result_backend

celery_app = Celery(
    "hvac_crm",
    broker=broker_url,
    backend=result_backend,
    include=[
        "app.workers.notifications",
        "app.workers.sla_monitor",
        "app.workers.task_notifications",
        "app.workers.reports",
        "app.workers.depreciation_calc",
        "app.workers.scheduled_tasks",
        "app.workers.tender_analysis",
        "app.workers.tender_smeta",
        "app.workers.task_due_rollover",
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
        "schedule": crontab(minute=f"*/{settings.celery_sla_check_every_minutes}"),
    },
    "calculate-monthly-depreciation": {
        "task": "app.workers.depreciation_calc.calculate_monthly_depreciation",
        "schedule": crontab(
            day_of_month=str(settings.celery_monthly_depreciation_day_of_month),
            hour=str(settings.celery_monthly_depreciation_hour),
            minute=str(settings.celery_monthly_depreciation_minute),
        ),
    },
    "send-daily-summary": {
        "task": "app.workers.reports.send_daily_summary",
        "schedule": crontab(
            hour=str(settings.celery_daily_summary_hour),
            minute=str(settings.celery_daily_summary_minute),
        ),
    },
    "check-overdue-tasks": {
        "task": "app.workers.sla_monitor.check_overdue_tasks",
        "schedule": crontab(minute=f"*/{settings.celery_overdue_check_every_minutes}"),
    },
    "scan-task-deadline-notifications": {
        "task": "app.workers.task_notifications.scan_task_deadlines",
        "schedule": crontab(minute=f"*/{settings.celery_task_notifications_scan_every_minutes}"),
    },
    "rollover-overdue-task-due-dates": {
        "task": "app.workers.task_due_rollover.run_task_due_rollover",
        "schedule": crontab(
            hour=str(settings.celery_task_due_rollover_hour),
            minute=str(settings.celery_task_due_rollover_minute),
        ),
    },
}

celery_app.conf.beat_schedule["create-env-scheduled-task"] = {
    "task": "app.workers.scheduled_tasks.create_env_scheduled_task",
    "schedule": crontab(minute="*"),
}
