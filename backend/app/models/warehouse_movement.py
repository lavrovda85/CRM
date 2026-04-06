"""Warehouse movement and reservation models.

Отслеживание прихода, расхода, списания, перемещения
материалов и резервирования под задачи.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WarehouseMovement(BaseModel):
    """Record of inventory movement (intake, consumption, write-off, transfer).

    Атрибуты:
        item_id: ID складской позиции.
        task_id: ID задачи (если списание привязано к задаче).
        user_id: ID пользователя, выполнившего операцию.
        movement_type: Тип движения (intake, consumption, write_off, transfer, return).
        quantity: Количество (положительное).
        unit_price: Цена за единицу на момент операции.
        reason: Причина / комментарий.
        destination: Место назначения (для перемещений).
    """

    __tablename__ = "warehouse_movements"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_items.id"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)

    item = relationship("WarehouseItem", back_populates="movements")
    task = relationship("Task")
    user = relationship("User")


class WarehouseReservation(BaseModel):
    """Material reservation linked to a specific task.

    Атрибуты:
        item_id: ID складской позиции.
        task_id: ID задачи.
        quantity: Зарезервированное количество.
        status: Статус резерва (reserved, consumed, cancelled).
    """

    __tablename__ = "warehouse_reservations"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_items.id"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="reserved")

    item = relationship("WarehouseItem", back_populates="reservations")
    task = relationship("Task", back_populates="reservations")
