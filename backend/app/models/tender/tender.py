"""Tender entity model.

Тендеры — отдельная от сделок сущность с собственным
жизненным циклом и привязкой задач.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class Tender(TenantMixin, BaseModel):
    """Tender/bid entity with its own lifecycle.

    Атрибуты:
        title: Название тендера.
        description: Описание тендера.
        source: Источник (площадка, заказчик).
        budget: Бюджет тендера.
        our_price: Наша ценовая заявка.
        status: Текущий статус (search, participation, won, lost, execution, completed).
        deadline: Крайний срок подачи заявки.
        execution_deadline: Крайний срок выполнения.
        assigned_to: Ответственный менеджер.
        requirements: Требования тендера (JSON).
        documents_url: Ссылка на тендерную документацию.
        notes: Заметки.
        tender_analysis: JSON с результатами ИИ-анализа документов (риски, рентабельность, ведомость работ).
    """

    __tablename__ = "tenders"

    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    our_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="search", index=True)
    deadline: Mapped[str | None] = mapped_column(Date, nullable=True)
    execution_deadline: Mapped[str | None] = mapped_column(Date, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    requirements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    documents_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    tender_link: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    guarantee_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    trade_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    trade_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tender_analysis: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    assignee = relationship("User", foreign_keys=[assigned_to])
    customer = relationship("Client")
    tasks = relationship("Task", back_populates="tender")
    documents = relationship("Document", back_populates="tender")
    comments = relationship(
        "TenderComment",
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="TenderComment.created_at",
    )
    checklists = relationship(
        "TenderChecklist",
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="TenderChecklist.created_at",
    )

    @property
    def customer_name(self) -> str | None:
        """Convenience field for API responses."""
        return self.customer.name if self.customer is not None else None
