"""Chat message model (company-wide employee chat).

The chat is separate from task comments and supports simple message history
for authenticated employees.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class ChatMessage(BaseModel):
    """Company chat message entity.

    Args:
        room: Chat room identifier (e.g. "company").
        sender_id: UUID of the message author.
        body: Message text.
    """

    __tablename__ = "chat_messages"

    room: Mapped[str] = mapped_column(default="company", index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    sender = relationship("User", back_populates="chat_messages")
    attachments = relationship(
        "ChatAttachment",
        back_populates="chat_message",
        cascade="all, delete-orphan",
        order_by="ChatAttachment.created_at",
    )

    @property
    def sender_name(self) -> str | None:
        """Convenience field for API responses."""
        return self.sender.full_name if self.sender is not None else None

