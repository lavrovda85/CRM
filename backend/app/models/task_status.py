"""Task status history tracking model.

Сохраняет историю всех переходов статусов задачи
для аудита и аналитики.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TaskStatusHistory(BaseModel):
    """Audit log entry for task status transitions.

    Атрибуты:
        task_id: ID задачи.
        from_status: Предыдущий статус.
        to_status: Новый статус.
        changed_by: ID пользователя, инициировавшего переход.
        reason: Комментарий к переходу.
        transition_data: Дополнительные данные перехода (заполненные чек-листы и т.д.).
    """

    __tablename__ = "task_status_history"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str] = mapped_column(String(100), nullable=False)
    to_status: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    transition_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    task = relationship("Task", back_populates="status_history")
    user = relationship("User", foreign_keys=[changed_by])
