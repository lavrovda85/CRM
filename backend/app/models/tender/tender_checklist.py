"""Tender checklist models.

Defines a per-tender checklist with items and completion tracking.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TenderChecklist(BaseModel):
    """Checklist container linked to a tender.

    Attributes:
        tender_id: Tender ID.
        title: Checklist title.
        items: Checklist items.
    """

    __tablename__ = "tender_checklists"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    items = relationship(
        "TenderChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="TenderChecklistItem.order",
    )

    tender = relationship("Tender", back_populates="checklists")


class TenderChecklistItem(BaseModel):
    """Single checklist item with completion and optional task linkage.

    Attributes:
        checklist_id: Parent checklist ID.
        title: Item title.
        item_type: Machine-readable item type.
        order: Sort order.
        is_completed: Completion flag.
        completed_by: User ID who completed the item.
        completed_at: Completion timestamp.
        calculation_task_id: Optional task ID for calculation-related item.
        scheduled_offset_hours: Optional offset (hours) from trade_start_at for scheduled checks.
    """

    __tablename__ = "tender_checklist_items"

    checklist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tender_checklists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    item_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_completed: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    calculation_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scheduled_offset_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    checklist = relationship("TenderChecklist", back_populates="items")

