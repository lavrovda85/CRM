"""Tender entity model.

Тендеры — отдельная от сделок сущность с собственным
жизненным циклом и привязкой задач.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Tender(BaseModel):
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignee = relationship("User", foreign_keys=[assigned_to])
    tasks = relationship("Task", back_populates="tender")
