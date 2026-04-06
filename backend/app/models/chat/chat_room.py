"""Chat room model (employee chat groups by direction, scoped to tenant company)."""

from sqlalchemy import String, Text, UniqueConstraint
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
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_chat_rooms_company_code"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

