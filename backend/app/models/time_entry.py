"""Time entry model for work time tracking.

Записи рабочего времени привязаны к задачам
и используются для расчёта зарплаты.
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class TimeEntry(TenantMixin, BaseModel):
    """Work time record linked to a task and user.

    Атрибуты:
        task_id: ID задачи.
        user_id: ID сотрудника.
        started_at: Время начала работы.
        ended_at: Время окончания работы.
        duration_minutes: Длительность в минутах (рассчитывается или вводится вручную).
        entry_type: Тип записи (timer, manual).
        is_billable: Оплачиваемое время.
        notes: Комментарий.
    """

    __tablename__ = "time_entries"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    is_billable: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    task = relationship("Task", back_populates="time_entries")
    user = relationship("User", back_populates="time_entries")
