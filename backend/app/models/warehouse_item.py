"""Warehouse item model for inventory management.

Складские позиции с отслеживанием количества,
резервов и минимального остатка.
"""

from decimal import Decimal

from sqlalchemy import Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WarehouseItem(BaseModel):
    """Inventory item tracked in the warehouse.

    Атрибуты:
        name: Название материала / товара.
        sku: Артикул (уникальный).
        category: Категория (materials, tools, consumables, equipment).
        unit: Единица измерения (pcs, m, kg, l).
        quantity: Текущее количество на складе.
        reserved_quantity: Зарезервированное под задачи количество.
        min_quantity: Минимальный остаток (для уведомлений).
        price: Цена за единицу.
        description: Описание.
        location: Место хранения на складе.
    """

    __tablename__ = "warehouse_items"

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="materials", index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False, default=0)
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False, default=0)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), nullable=False, default=0)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    movements = relationship("WarehouseMovement", back_populates="item")
    reservations = relationship("WarehouseReservation", back_populates="item")
