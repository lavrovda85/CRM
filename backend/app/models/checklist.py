"""Checklist and checklist item models for task gating.

Чек-листы привязаны к задачам и блокируют переходы
статусов до полного заполнения.
"""

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Checklist(BaseModel):
    """Task-level checklist that may gate a workflow transition.

    Атрибуты:
        task_id: ID задачи.
        title: Название чек-листа.
        gate_transition: Переход, блокируемый этим чек-листом (from->to).
        is_completed: Все пункты выполнены.
    """

    __tablename__ = "checklists"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    gate_transition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    task = relationship("Task", back_populates="checklists")
    items = relationship("ChecklistItem", back_populates="checklist", cascade="all, delete-orphan",
                         order_by="ChecklistItem.order")


class ChecklistItem(BaseModel):
    """Individual item within a checklist.

    Атрибуты:
        checklist_id: ID чек-листа.
        title: Текст пункта.
        is_completed: Пункт выполнен.
        completed_by: ID пользователя, отметившего выполнение.
        completed_at: Время выполнения.
        order: Порядок отображения.
    """

    __tablename__ = "checklist_items"

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order: Mapped[int] = mapped_column(default=0)

    checklist = relationship("Checklist", back_populates="items")
    completer = relationship("User", foreign_keys=[completed_by])
