"""Dynamic reference/dictionary models.

Управляемые через UI и MCP справочники:
материалы, услуги, типы работ и т.д.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class Reference(TenantMixin, BaseModel):
    """Dynamic dictionary/reference table.

    Атрибуты:
        code: Машинное имя справочника (materials, services, work_types, etc.).
        name: Человекочитаемое название.
        description: Описание назначения справочника.
        is_system: Системный справочник (нельзя удалить).
    """

    __tablename__ = "references"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_references_company_code"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    items = relationship("ReferenceItem", back_populates="reference", cascade="all, delete-orphan",
                         order_by="ReferenceItem.order")


class ReferenceItem(TenantMixin, BaseModel):
    """Item within a dynamic reference dictionary.

    Атрибуты:
        reference_id: ID справочника.
        code: Машинное имя элемента.
        name: Отображаемое название.
        metadata: Дополнительные атрибуты (единицы, цена, и т.д.).
        order: Порядок сортировки.
        is_active: Активен ли элемент.
    """

    __tablename__ = "reference_items"

    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("references.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reference = relationship("Reference", back_populates="items")
