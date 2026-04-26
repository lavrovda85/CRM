"""Equipment and usage tracking models.

Учёт инструмента и оборудования с отслеживанием
износа, текущей стоимости и привязки к задачам.
"""

import uuid
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class Equipment(TenantMixin, BaseModel):
    """Equipment/tool asset with depreciation tracking.

    Атрибуты:
        name: Название оборудования.
        serial_number: Серийный номер (уникальный).
        category: Категория (power_tool, measuring, hand_tool, instrument, safety, vehicle, automobile, crew).
        purchase_price: Цена покупки.
        purchase_date: Дата покупки.
        service_life_months: Расчётный срок службы в месяцах.
        current_value: Текущая остаточная стоимость.
        status: Статус (active, maintenance, written_off, lost).
        assigned_to: Закреплено за сотрудником.
        location: Местонахождение.
        notes: Заметки.
    """

    __tablename__ = "equipment"
    __table_args__ = (UniqueConstraint("company_id", "serial_number", name="uq_equipment_company_serial"),)

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    serial_number: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="hand_tool", index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    purchase_date: Mapped[str] = mapped_column(Date, nullable=False)
    service_life_months: Mapped[int] = mapped_column(Integer, nullable=False, default=36)
    current_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    hourly_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        doc="Optional cost per hour (e.g. crew / subcontractor modeled as equipment).",
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    holder = relationship("User", foreign_keys=[assigned_to])
    depreciation_records = relationship("DepreciationRecord", back_populates="equipment",
                                         order_by="DepreciationRecord.created_at")
    usage_records = relationship("EquipmentUsage", back_populates="equipment")


class EquipmentUsage(TenantMixin, BaseModel):
    """Record of equipment usage on a specific task.

    Атрибуты:
        equipment_id: ID оборудования.
        task_id: ID задачи.
        user_id: ID пользователя.
        hours_used: Количество часов использования.
        notes: Заметки.
    """

    __tablename__ = "equipment_usage"

    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    hours_used: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment = relationship("Equipment", back_populates="usage_records")
    task = relationship("Task", back_populates="equipment_usage")
    user = relationship("User")
