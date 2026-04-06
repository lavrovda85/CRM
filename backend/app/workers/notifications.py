"""Notification delivery background tasks.

Отправляет уведомления через Telegram и Web Push
в фоновом режиме через Celery.
"""

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.workers.notifications.send_telegram_notification")
def send_telegram_notification(user_id: str, message: str) -> dict:
    """Send a Telegram notification to a user.

    Аргументы:
        user_id: ID пользователя для отправки.
        message: Текст уведомления.

    Возвращает:
        Статус доставки.
    """
    logger.info("Sending Telegram notification", user_id=user_id)
    # TODO: implement via python-telegram-bot
    return {"status": "sent", "user_id": user_id}


@celery_app.task(name="app.workers.notifications.send_task_notification")
def send_task_notification(task_id: str, event: str, recipients: list[str]) -> dict:
    """Send task-related notifications to specified recipients.

    Аргументы:
        task_id: ID задачи.
        event: Тип события (created, status_changed, comment_added).
        recipients: Список ID получателей.

    Возвращает:
        Статус доставки для каждого получателя.
    """
    logger.info("Sending task notification", task_id=task_id, event=event, count=len(recipients))
    return {"status": "sent", "task_id": task_id, "event": event}
