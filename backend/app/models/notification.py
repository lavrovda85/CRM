"""Notification model for delivery tracking.

Отслеживание уведомлений, отправленных через различные
каналы (Telegram, Web Push, Email).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Notification(BaseModel):
    """Notification delivery record.

    Атрибуты:
        user_id: ID получателя.
        channel: Канал доставки (telegram, web_push, email).
        event_type: Тип события (task_assigned, status_changed, sla_warning, etc.).
        title: Заголовок уведомления.
        body: Текст уведомления.
        data: Дополнительные данные (task_id, link, etc.).
        is_read: Прочитано ли уведомление.
        is_delivered: Доставлено ли уведомление.
    """

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, default="web_push")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user = relationship("User", foreign_keys=[user_id])
