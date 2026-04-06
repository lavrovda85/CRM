"""Chat attachment model.

Stores files attached to a chat message (including voice recordings).
"""

import uuid

from sqlalchemy import ForeignKey, String, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Text

from app.models.base import BaseModel


class ChatAttachment(BaseModel):
    """Attachment linked to a chat message.

    Args:
        chat_message_id: UUID of the parent chat message.
        uploaded_by: UUID of the user who uploaded the file.
        filename: Original filename.
        storage_path: MinIO object key (bucket/key path).
        mime_type: MIME type (e.g. "audio/webm", "application/pdf").
        file_size: File size in bytes.
    """

    __tablename__ = "chat_attachments"

    chat_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    chat_message = relationship("ChatMessage", back_populates="attachments")
    uploader = relationship("User")

