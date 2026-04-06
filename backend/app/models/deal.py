"""Deal and pipeline stage models for CRM.

Сделки проходят по стадиям воронки продаж,
привязаны к клиентам и ответственным менеджерам.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class DealStage(TenantMixin, BaseModel):
    """Pipeline stage definition for deals.

    Атрибуты:
        name: Название стадии.
        order: Порядковый номер в воронке.
        color: HEX цвет для UI.
        is_won: Признак выигранной сделки.
        is_lost: Признак потерянной сделки.
    """

    __tablename__ = "deal_stages"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    is_won: Mapped[bool] = mapped_column(default=False)
    is_lost: Mapped[bool] = mapped_column(default=False)

    deals = relationship("Deal", back_populates="stage")


class Deal(TenantMixin, BaseModel):
    """Sales deal entity in the CRM pipeline.

    Атрибуты:
        client_id: ID клиента.
        title: Название сделки.
        description: Описание.
        amount: Сумма сделки.
        stage_id: Текущая стадия воронки.
        assigned_to: Ответственный менеджер.
        expected_close: Ожидаемая дата закрытия.
        source: Источник сделки.
    """

    __tablename__ = "deals"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_stages.id"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    expected_close: Mapped[str | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    client = relationship("Client", back_populates="deals")
    stage = relationship("DealStage", back_populates="deals")
    assignee = relationship("User", foreign_keys=[assigned_to])
    tasks = relationship("Task", back_populates="deal")
