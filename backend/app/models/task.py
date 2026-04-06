"""Core Task model — the central entity of the platform.

Задачи создаются из шаблонов, привязаны к клиентам,
сделкам или тендерам и проходят через workflow.
"""

import uuid
from datetime import datetime

from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseModel, TenantMixin

# Visibility: whole company vs. only people involved in the task.
TASK_VISIBILITY_COMPANY = "company"
TASK_VISIBILITY_PARTICIPANTS = "participants"
ALLOWED_TASK_VISIBILITIES: frozenset[str] = frozenset(
    {TASK_VISIBILITY_COMPANY, TASK_VISIBILITY_PARTICIPANTS}
)

task_co_assignees = Table(
    "task_co_assignees",
    Base.metadata,
    Column("task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

task_observers = Table(
    "task_observers",
    Base.metadata,
    Column("task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Task(TenantMixin, BaseModel):
    """Central task entity created from templates.

    Атрибуты:
        template_id: ID шаблона, из которого создана задача.
        board_id: ID доски для отображения.
        client_id: ID клиента.
        deal_id: ID сделки (если привязана).
        tender_id: ID тендера (если привязана).
        assigned_to: ID исполнителя.
        created_by: ID пользователя, создавшего запись (аудит).
        requested_by: ID постановщика задачи (если NULL — в API как создатель).
        title: Заголовок задачи.
        description: Описание.
        status: Текущий статус (из workflow_definition шаблона).
        priority: Приоритет (low, medium, high, critical).
        custom_fields: Заполненные кастомные поля (key -> value).
        due_date: Крайний срок выполнения.
        started_at: Фактическое время начала работы.
        completed_at: Фактическое время завершения.
        sla_deadline: Крайний срок по SLA.
        deleted_at: Метка мягкого удаления (NULL — задача активна).
        deleted_by: Кто выполнил мягкое удаление.
        visibility: company — видна всей компании; participants — только участникам задачи.
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
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
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

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TASK_VISIBILITY_COMPANY,
        server_default=TASK_VISIBILITY_COMPANY,
        index=True,
    )

    @classmethod
    def active_filter(cls) -> Any:
        """Return SQLAlchemy clause: task is not soft-deleted (``deleted_at`` is NULL)."""
        return cls.deleted_at.is_(None)

    template = relationship("TaskTemplate", back_populates="tasks")
    board = relationship("Board", back_populates="tasks")
    client = relationship("Client", back_populates="tasks")
    deal = relationship("Deal", back_populates="tasks")
    tender = relationship("Tender", back_populates="tasks")
    assignee = relationship("User", back_populates="assigned_tasks", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])
    requester_user = relationship("User", foreign_keys=[requested_by])
    co_assignees = relationship(
        "User",
        secondary=task_co_assignees,
        back_populates="co_assigned_tasks",
    )
    observers = relationship(
        "User",
        secondary=task_observers,
        back_populates="observed_tasks",
    )

    # passive_deletes: DB FK uses ON DELETE CASCADE — do not NULL out child.task_id on parent delete.
    status_history = relationship(
        "TaskStatusHistory",
        back_populates="task",
        order_by="TaskStatusHistory.created_at",
        passive_deletes=True,
    )
    checklists = relationship("Checklist", back_populates="task", cascade="all, delete-orphan")
    time_entries = relationship("TimeEntry", back_populates="task", passive_deletes=True)
    documents = relationship("Document", back_populates="task")
    comments = relationship(
        "Comment",
        back_populates="task",
        order_by="Comment.created_at",
        passive_deletes=True,
    )
    # ORM deletes these first; DB constraints may lack ON DELETE CASCADE on older schemas.
    reservations = relationship(
        "WarehouseReservation",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    equipment_usage = relationship(
        "EquipmentUsage",
        back_populates="task",
        cascade="all, delete-orphan",
    )
