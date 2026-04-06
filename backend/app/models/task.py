"""Core Task model — the central entity of the platform.

Задачи создаются из шаблонов, привязаны к клиентам,
сделкам или тендерам и проходят через workflow.
"""

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Task(BaseModel):
    """Central task entity created from templates.

    Атрибуты:
        template_id: ID шаблона, из которого создана задача.
        board_id: ID доски для отображения.
        client_id: ID клиента.
        deal_id: ID сделки (если привязана).
        tender_id: ID тендера (если привязана).
        assigned_to: ID исполнителя.
        created_by: ID создателя задачи.
        title: Заголовок задачи.
        description: Описание.
        status: Текущий статус (из workflow_definition шаблона).
        priority: Приоритет (low, medium, high, critical).
        custom_fields: Заполненные кастомные поля (key -> value).
        due_date: Крайний срок выполнения.
        started_at: Фактическое время начала работы.
        completed_at: Фактическое время завершения.
        sla_deadline: Крайний срок по SLA.
    """

    __tablename__ = "tasks"

    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_templates.id"), nullable=True, index=True
    )
    board_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("boards.id"), nullable=True, index=True
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True, index=True
    )
    tender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=True, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="new", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    due_date: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    template = relationship("TaskTemplate", back_populates="tasks")
    board = relationship("Board", back_populates="tasks")
    client = relationship("Client", back_populates="tasks")
    deal = relationship("Deal", back_populates="tasks")
    tender = relationship("Tender", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])

    status_history = relationship("TaskStatusHistory", back_populates="task", order_by="TaskStatusHistory.created_at")
    checklists = relationship("Checklist", back_populates="task", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="task")
    documents = relationship("Document", back_populates="task")
    comments = relationship("Comment", back_populates="task", order_by="Comment.created_at")
    reservations = relationship("WarehouseReservation", back_populates="task")
    equipment_usage = relationship("EquipmentUsage", back_populates="task")
