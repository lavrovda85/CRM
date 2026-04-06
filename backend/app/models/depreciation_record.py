"""Depreciation record model for equipment amortization.

Ежемесячные записи амортизации оборудования
с использованием линейного метода начисления.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class DepreciationRecord(TenantMixin, BaseModel):
    """Monthly depreciation entry for an equipment item.

    Атрибуты:
        equipment_id: ID оборудования.
        period_date: Дата периода начисления (первое число месяца).
        amount: Сумма амортизации за период.
        accumulated: Накопленная амортизация.
        remaining_value: Остаточная стоимость после начисления.
        method: Метод начисления (straight_line, declining_balance).
        notes: Комментарий.
    """

    __tablename__ = "depreciation_records"

    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_date: Mapped[str] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    accumulated: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    remaining_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False, default="straight_line")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment = relationship("Equipment", back_populates="depreciation_records")
