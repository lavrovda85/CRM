"""Chat room model (employee chat groups by direction, scoped to tenant company)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, TenantMixin


class ChatRoom(TenantMixin, BaseModel):
    """Chat room definition.

    The `code` is used as `room` key in `chat_messages`.

    Args:
        name: Human readable room name (e.g. direction name).
        code: Stable unique room code (e.g. "company", "montage").
    """

    __tablename__ = "chat_rooms"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_chat_rooms_company_code"),
        UniqueConstraint("company_id", "task_id", name="uq_chat_rooms_company_task"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    participant_user_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

